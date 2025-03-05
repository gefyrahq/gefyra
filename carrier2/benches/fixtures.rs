use carrier2::GefyraClient;
use pingora::http::{Method, RequestHeader};

pub fn get_gefyra_clients(amount: u32) -> Vec<GefyraClient> {
    let mut yaml = "".to_string();

    for x in 1..amount {
        let user = format!(
            "
        user-{n}: 
            endpoint: \"www.blueshoe.io:443\" 
            tls: true 
            sni: \"www.blueshoe.io\" 
            rules: 
                - match: 
                    - matchHeader: 
                        name: \"x-gefyra\" 
                        value: \"user-{n}\"
                    - matchPath: 
                        path: \"/my-pyth\"
                        type: \"prefix\"
                - match:
                    - matchPath:
                        path: \"/always-{n}\"
                        type: \"prefix\"
        ",
            n = x
        );
        yaml.push_str(&user);
    }

    let mapping1 = serde_yaml::from_str(&yaml).unwrap();
    GefyraClient::from_yaml(&mapping1, false, "".to_string())
}

pub fn get_simple_header(amount: u32, path: String) -> RequestHeader {
    let mut req1 = RequestHeader::build(Method::GET, path.as_bytes(), None).unwrap();

    for x in 1..amount {
        req1.append_header(format!("header-{}", x), format!("value-{}", x))
            .unwrap();
        req1.append_header("x-gefyra", format!("user-{}", x))
            .unwrap();
    }
    req1
}
