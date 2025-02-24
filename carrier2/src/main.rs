use async_trait::async_trait;
use log::{debug, info};
use matching::GefyraClient;
use pingora::{prelude::*, server::configuration::ServerConf};

use std::{fs, path::Path, sync::Arc};

mod matching;

pub struct Carrier2 {
    cluster_upstream: Option<Arc<LoadBalancer<RoundRobin>>>,
    cluster_tls: bool,
    cluster_sni: String,
    gefyra_clients: Arc<Vec<GefyraClient>>,
}

#[async_trait]
impl ProxyHttp for Carrier2 {
    type CTX = ();
    fn new_ctx(&self) -> () {
        ()
    }

    async fn upstream_peer(&self, _session: &mut Session, _ctx: &mut ()) -> Result<Box<HttpPeer>> {
        let client_idx = self
            .gefyra_clients
            .iter()
            .position(|c| c.matching_rules.is_hit(_session.req_header()));
        if let Some(client_idx) = client_idx {
            let client = &self.gefyra_clients[client_idx];
            info!("Selected GefyraClient {:?}", client.key);
            return Ok(Box::new(client.peer.clone()));
        }

        if let Some(cluster_lb) = &self.cluster_upstream {
            let cluster_peer = cluster_lb.select(b"", 256).unwrap();
            let peer = Box::new(HttpPeer::new(
                cluster_peer,
                self.cluster_tls,
                self.cluster_sni.clone(),
            ));
            info!("Selected cluster upstream peer");
            return Ok(peer);
        }
        Err(Box::new(pingora::Error {
            etype: todo!(),
            esource: todo!(),
            retry: todo!(),
            cause: todo!(),
            context: todo!(),
        }))
    }
}

fn main() {
    env_logger::init();

    // parse arguments from CLI
    let args = Opt::parse_args();
    // TODO lots of unwraps here
    let conf_file = args.conf.clone().unwrap();
    let conf_str = fs::read_to_string(conf_file.clone()).unwrap();
    let conf_data: serde_yaml::Value = serde_yaml::from_str(conf_str.as_str()).unwrap();
    let server_conf: ServerConf = serde_yaml::from_str(conf_str.as_str()).unwrap();
    // gefyra bridge file
    let bridge_data = if conf_data.as_mapping().unwrap().contains_key("bridge_file") {
        let gefyra_file_path = Path::new(&conf_file)
            .parent()
            .unwrap()
            .join(conf_data["bridge_file"].as_str().unwrap());
        let gefyra_bridge_str = fs::read_to_string(gefyra_file_path).unwrap();
        let bridge_data: serde_yaml::Value =
            serde_yaml::from_str(gefyra_bridge_str.as_str()).unwrap();
        Some(bridge_data)
    } else {
        None
    };

    // init and boostrap pingora server
    let mut my_server = Server::new_with_opt_and_conf(Some(args), server_conf);
    my_server.bootstrap();

    debug!("{:?}", my_server.configuration);
    debug!("GefyraBrige config: {:?}", bridge_data);

    if let None = bridge_data {
        // no GefyraBridge data given, run without actually doing anything
        my_server.run_forever();
    } else if let Some(bridge_data) = bridge_data {
        // GefyraBridge data given, run the proxy process
        let bridge_data = bridge_data.as_mapping().unwrap();
        // read the cluster upstream
        let cluster_upstreams = if bridge_data.contains_key("clusterUpstream") {
            let addresss: Vec<String> = bridge_data["clusterUpstream"]["peers"]
                .as_sequence()
                .unwrap()
                .iter()
                .map(|a| a.as_str().unwrap().to_string())
                .collect();
            Some(Arc::new(LoadBalancer::try_from_iter(addresss).unwrap()))
        } else {
            None
        };

        let clients = GefyraClient::from_yaml(bridge_data["bridges"].as_mapping().unwrap());

        let carrier2_http_router = Carrier2 {
            cluster_upstream: cluster_upstreams,
            gefyra_clients: Arc::new(clients),
            cluster_tls: bridge_data["clusterUpstream"]["tls"].as_bool().unwrap(),
            cluster_sni: bridge_data["clusterUpstream"]["sni"]
                .as_str()
                .unwrap()
                .to_string(),
        };

        let mut http_dispatcher =
            http_proxy_service(&my_server.configuration, carrier2_http_router);
        // add listening port
        http_dispatcher
            .add_tcp(format!("0.0.0.0:{}", bridge_data["port"].as_u64().unwrap()).as_str());

        // add http dispatcher server
        my_server.add_service(http_dispatcher);

        // run this friend forever (until the next upgrade)
        my_server.run_forever();
    };
}
