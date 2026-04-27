use async_trait::async_trait;
use http::{HeaderValue, Response, StatusCode};
use lib::GefyraClient;
use log::{debug, error, info, warn};
use pingora::{
    apps::http_app::ServeHttp, prelude::*, protocols::http::ServerSession,
    server::configuration::ServerConf, services::listening::Service,
};
use uuid::Uuid;

use std::{fs, sync::Arc};

pub mod lib;

pub struct Carrier2 {
    cluster_upstream: Option<Arc<LoadBalancer<RoundRobin>>>,
    cluster_tls: bool,
    cluster_sni: String,
    gefyra_clients: Arc<Vec<GefyraClient>>,
    logging_headers: Vec<String>,
}

pub struct Carrier2Ctx {
    request_id: String,
    external_request_id: Option<String>,
}

impl Carrier2Ctx {
    fn get_request_id(&self) -> &String {
        match self.external_request_id {
            Some(ref header) => header,
            None => &self.request_id,
        }
    }
}

#[async_trait]
impl ProxyHttp for Carrier2 {
    type CTX = Carrier2Ctx;
    fn new_ctx(&self) -> Self::CTX {
        Carrier2Ctx {
            request_id: Uuid::new_v4().to_string(),
            external_request_id: None,
        }
    }

    fn fail_to_connect(
        &self,
        _session: &mut Session,
        _peer: &HttpPeer,
        _ctx: &mut Self::CTX,
        e: Box<Error>,
    ) -> Box<Error> {
        error!(
            "({}) Error connecting upstream request: {}",
            _ctx.get_request_id(),
            e
        );
        e
    }

    async fn request_filter(&self, session: &mut Session, ctx: &mut Self::CTX) -> Result<bool> {
        let mut external_req_id: Option<String> = None;
        for logging_header in self.logging_headers.iter() {
            let external_header_req_id = session.get_header(logging_header);
            match external_header_req_id {
                Some(value) => {
                    external_req_id =
                        Some(format!("{}:{}", logging_header, value.to_str().unwrap()));
                    break;
                }
                None => continue,
            }
        }

        ctx.external_request_id = external_req_id;

        if let Some(client) = session.client_addr() {
            info!(
                "({}) Received request from {}",
                ctx.get_request_id(),
                client
            );
        }
        Ok(false)
    }

    async fn logging(
        &self,
        session: &mut Session,
        _e: Option<&pingora::Error>,
        ctx: &mut Self::CTX,
    ) {
        let response_code = session
            .response_written()
            .map_or(0, |resp| resp.status.as_u16());
        // access log
        info!(
            "({}) {} response code: {response_code}",
            ctx.get_request_id(),
            self.request_summary(session, ctx)
        );
    }

    async fn upstream_peer(
        &self,
        _session: &mut Session,
        _ctx: &mut Carrier2Ctx,
    ) -> Result<Box<HttpPeer>> {
        let client_idx = self
            .gefyra_clients
            .iter()
            .position(|c| c.matching_rules.is_hit(_session.req_header()));
        if let Some(client_idx) = client_idx {
            let client = &self.gefyra_clients[client_idx];
            info!(
                "({}) Selected GefyraClient {:?}",
                _ctx.get_request_id(),
                client.key
            );
            return Ok(Box::new(client.peer.clone()));
        }

        if let Some(cluster_lb) = &self.cluster_upstream {
            let cluster_peer = cluster_lb.select(b"", 256).unwrap();
            let peer = Box::new(HttpPeer::new(
                cluster_peer,
                self.cluster_tls,
                self.cluster_sni.clone(),
            ));
            if self.gefyra_clients.len() == 0 {
                info!(
                    "({}) Selected cluster upstream (no GefyraClient loaded)",
                    _ctx.get_request_id()
                );
            } else {
                info!(
                    "({}) Selected cluster upstream (no matching rule hit)",
                    _ctx.get_request_id()
                );
            }

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

pub struct HttpGetProbeHandler;

#[async_trait]
impl ServeHttp for HttpGetProbeHandler {
    async fn response(&self, _: &mut ServerSession) -> Response<Vec<u8>> {
        Response::builder()
            .status(StatusCode::OK)
            .header(http::header::CONTENT_LENGTH, 0)
            .body(vec![])
            .unwrap()
    }
}

fn main() {
    let _ = env_logger::builder()
        .filter_level(log::LevelFilter::Info)
        .format_timestamp_nanos()
        .try_init();

    // parse arguments from CLI
    let args = Opt::parse_args();
    // TODO lots of unwraps here
    let conf_file = args.conf.clone();
    // GO-1033: support external request header to instrument log output
    let supported_logging_headers = vec![
        "opc-request-id".to_string(),
        "x-amzn-trace-id".to_string(),
        "x-cloud-trace-context".to_string(),
        "request-id".to_string(),
        "x-ms-request-id".to_string(),
    ];
    let my_server = if let Some(conf_file) = conf_file {
        let conf_str = fs::read_to_string(conf_file.clone()).unwrap();
        let carrier_config: serde_yaml::Value = serde_yaml::from_str(conf_str.as_str()).unwrap();
        let server_conf: ServerConf = serde_yaml::from_str(conf_str.as_str()).unwrap();
        // init and boostrap pingora server
        let mut my_server = Server::new_with_opt_and_conf(Some(args), server_conf);
        my_server.bootstrap();

        debug!("{:?}", my_server.configuration);
        debug!("GefyraBridge config: {:?}", carrier_config);
        let carrier_config = carrier_config.as_mapping().unwrap();

        // GefyraBridge data given, run the proxy process
        if carrier_config.contains_key("proxy") {
            // init mutliple proxies on different ports
            if let Some(proxy) = carrier_config.get("proxy") {
                let proxies = proxy.as_sequence().unwrap();
                info!("Configure {:?} proxy", proxies.len());
                for proxy in proxies {
                    let mut cert_path: Option<String> = None;
                    let mut key_path: Option<String> = None;
                    let mut local_sni: Option<String> = None;
                    let proxy = proxy.as_mapping().unwrap();
                    // read the cluster upstream
                    let cluster_upstreams = if proxy.contains_key("clusterUpstream") {
                        let addresss: Vec<String> = proxy["clusterUpstream"]
                            .as_sequence()
                            .unwrap()
                            .iter()
                            .map(|a| a.as_str().unwrap().to_string())
                            .collect();
                        Some(Arc::new(LoadBalancer::try_from_iter(addresss).unwrap()))
                    } else {
                        None
                    };

                    if proxy.contains_key("tls") {
                        cert_path = match proxy["tls"]["certificate"].as_str() {
                            Some(path) => Some(path.into()),
                            None => {
                                warn!("'tls' is set, but 'certificate' is missing");
                                None
                            }
                        };
                        key_path = match proxy["tls"]["key"].as_str() {
                            Some(path) => Some(path.into()),
                            None => {
                                warn!("'tls' is set, but 'key' is missing");
                                None
                            }
                        };
                        local_sni = match proxy["tls"]["sni"].as_str() {
                            Some(path) => Some(path.into()),
                            None => {
                                warn!("'tls' is set, but 'sni' is missing");
                                None
                            }
                        };
                    }

                    let clients = if proxy.contains_key("bridges") {
                        GefyraClient::from_yaml(
                            proxy["bridges"].as_mapping().unwrap(),
                            cert_path.is_some() && key_path.is_some(),
                            local_sni.clone().unwrap_or_else(|| "".to_string()),
                        )
                    } else {
                        Vec::new()
                    };

                    let carrier2_http_router = Carrier2 {
                        cluster_upstream: cluster_upstreams,
                        gefyra_clients: Arc::new(clients),
                        cluster_tls: cert_path.is_some(),
                        cluster_sni: local_sni.unwrap_or_else(|| "".to_string()),
                        logging_headers: supported_logging_headers.clone(),
                    };

                    let mut http_dispatcher =
                        http_proxy_service(&my_server.configuration, carrier2_http_router);
                    // set listening addr
                    if proxy.contains_key("port") {
                        let listening = format!("0.0.0.0:{}", proxy["port"].as_u64().unwrap());
                        if cert_path.is_some() && key_path.is_some() {
                            // add tls setting
                            info!(
                                "Running with tls config: key {:?} cert {:?}",
                                key_path, cert_path
                            );
                            http_dispatcher
                                .add_tls(&listening, &cert_path.unwrap(), &key_path.unwrap())
                                .unwrap();
                        } else {
                            // add listening port (no tls)
                            http_dispatcher.add_tcp(&listening);
                        }

                        // add http dispatcher server
                        my_server.add_service(http_dispatcher);
                    }
                }
            }
        }

        // configure probes
        if carrier_config.contains_key("probes") {
            // httpGet probe
            if let Some(http_get_ports) = carrier_config["probes"].get("httpGet") {
                let ports = http_get_ports.as_sequence().unwrap();
                info!("Configured httpGet (scheme HTTP) probe ports: {:?}", ports);
                for port in ports {
                    let mut httpget_probe_handler = Service::new(
                        format!("httpGet probe handler {}", port.as_u64().unwrap()),
                        HttpGetProbeHandler,
                    );
                    httpget_probe_handler.add_tcp(&format!("0.0.0.0:{}", port.as_u64().unwrap()));
                    my_server.add_service(httpget_probe_handler);
                }
            }
            if let Some(https_get_ports) = carrier_config["probes"].get("httpsGet") {
                let ports = https_get_ports.as_sequence().unwrap();
                info!(
                    "Configured httpsGet (scheme HTTPS) probe ports: {:?}",
                    ports
                );
                for port in ports {
                    let mut httpsget_probe_handler = Service::new(
                        format!("httpsGet probe handler {}", port.as_u64().unwrap()),
                        HttpGetProbeHandler,
                    );
                    let listening = format!("0.0.0.0:{}", port.as_u64().unwrap());
                    httpsget_probe_handler
                        .add_tls(&listening, "/tmp/client-cert.pem", "/tmp/client-key.pem")
                        .unwrap();
                    my_server.add_service(httpsget_probe_handler);
                }
            }
        }
        my_server
    } else {
        warn!("No configuration provided. Idle mode ...");
        let mut my_server = Server::new(Some(args)).unwrap();
        my_server.bootstrap();
        my_server
    };

    // run this friend forever (until the next upgrade)
    my_server.run_forever();
}
