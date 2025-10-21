use log::debug;
use pingora::{http::RequestHeader, prelude::HttpPeer};
use regex::Regex;
use serde::Deserialize;
use serde_yaml::Mapping;

#[derive(Debug, PartialEq, Deserialize, Default, Clone)]
pub enum MatchType {
    #[default]
    #[serde(rename = "exact")]
    ExactLookup,
    #[serde(rename = "prefix")]
    PrefixLookup,
    #[serde(rename = "regex")]
    RegexLookup,
}

#[derive(Debug, PartialEq, Deserialize, Clone)]
pub struct MatchPath {
    path: String,
    #[serde(rename = "type")]
    match_type: MatchType,
}
impl MatchPath {
    fn is_hit(&self, query: &str) -> bool {
        match self.match_type {
            MatchType::PrefixLookup => query.starts_with(&self.path),
            MatchType::RegexLookup => Regex::new(self.path.as_str()).unwrap().is_match(query),
            MatchType::ExactLookup => self.path == query,
        }
    }
}

#[derive(Debug, PartialEq, Deserialize, Clone)]
pub struct MatchHeader {
    name: String,
    value: String,
    #[serde(rename = "type", default = "MatchType::default")]
    match_type: MatchType,
}
impl MatchHeader {
    fn is_hit(&self, name: &str, value: &str) -> bool {
        match self.match_type {
            MatchType::PrefixLookup => self.name == name && value.starts_with(&self.value),
            MatchType::RegexLookup => {
                Regex::new(self.name.as_str()).unwrap().is_match(name)
                    && Regex::new(self.value.as_str()).unwrap().is_match(value)
            }
            MatchType::ExactLookup => self.name == name && self.value == value,
        }
    }
}

#[derive(Debug, PartialEq, Deserialize, Clone)]
pub enum MatchRule {
    #[serde(rename = "matchPath")]
    Path(MatchPath),
    #[serde(rename = "matchHeader")]
    Header(MatchHeader),
}

#[derive(Debug, PartialEq, Deserialize, Clone)]
pub struct MatchAndCondition {
    #[serde(rename = "match")]
    #[serde(with = "serde_yaml::with::singleton_map_recursive")]
    and_match: Vec<MatchRule>,
}
impl MatchAndCondition {
    pub fn is_hit(&self, req: &RequestHeader) -> bool {
        let mut hit = true;
        for cond in &self.and_match {
            hit = hit
                && match cond {
                    MatchRule::Path(match_path) => {
                        match_path.is_hit(req.uri.path_and_query().unwrap().as_str())
                    }
                    MatchRule::Header(match_header) => {
                        let mut header_hit = false;
                        // TODO only limit to interesting headers from configuration
                        for (header_name, header_value) in req.headers.iter() {
                            // return after the first hit
                            header_hit = header_hit
                                || match_header
                                    .is_hit(header_name.as_str(), header_value.to_str().unwrap());
                        }
                        header_hit
                    }
                }
        }
        hit
    }
}

#[derive(Debug, PartialEq, Deserialize, Clone)]
pub struct MatchOrCondition {
    #[serde(rename = "rules")]
    or_rules: Vec<MatchAndCondition>,
}
impl MatchOrCondition {
    pub fn is_hit(&self, req: &RequestHeader) -> bool {
        let mut hit = false;
        for cond in &self.or_rules {
            hit = hit || cond.is_hit(req);
        }
        hit
    }
}

#[derive(Debug, Clone)]
pub struct GefyraClient {
    pub key: String,
    pub peer: HttpPeer,
    pub matching_rules: MatchOrCondition,
}
impl GefyraClient {
    pub fn from_yaml(value: &Mapping, default_tls_on: bool, sni: String) -> Vec<GefyraClient> {
        let mut clients = Vec::new();
        for (key, value) in value.iter() {
            debug!("GefyraClient with values {:?}", value);
            // todo this must be error checked
            let tls = value["tls"].as_bool().unwrap_or_else(|| default_tls_on);
            let sni = value["sni"].as_str().unwrap_or_else(|| &sni).to_string();
            let client = GefyraClient {
                key: key.as_str().unwrap().to_string(),
                peer: HttpPeer::new(value["endpoint"].as_str().unwrap(), tls, sni),
                matching_rules: serde_yaml::from_value(value.clone()).unwrap(),
            };
            debug!("Adding GefyraClient {:?}", client);
            clients.push(client);
        }
        clients
    }
}

#[cfg(test)]
mod tests {
    use pingora::{
        http::{Method, RequestHeader},
        upstreams::peer::Peer,
    };

    use super::{
        GefyraClient, MatchAndCondition, MatchHeader, MatchOrCondition, MatchPath, MatchRule,
        MatchType,
    };

    #[test]
    fn match_path() {
        let m1 = MatchPath {
            path: "/my-path_123".to_string(),
            match_type: MatchType::ExactLookup,
        };
        assert!(m1.is_hit("/my-path_123"));
        assert!(!m1.is_hit("/my-path_1234"));
        assert!(!m1.is_hit("/my-path_123?query=1234"));

        let m2 = MatchPath {
            path: "/my-path_123".to_string(),
            match_type: MatchType::PrefixLookup,
        };
        assert!(m2.is_hit("/my-path_123"));
        assert!(m2.is_hit("/my-path_1234"));
        assert!(m2.is_hit("/my-path_123?query=1234"));
        assert!(!m2.is_hit("/other-path_123"));

        let regex1 = MatchPath {
            path: "^/".to_string(),
            match_type: MatchType::RegexLookup,
        };
        assert!(regex1.is_hit("/my-path_123/456"));
        assert!(regex1.is_hit("/"));
        assert!(!regex1.is_hit("#123"));

        let regex2 = MatchPath {
            path: "^/[a-z0-9-.]".to_string(),
            match_type: MatchType::RegexLookup,
        };
        assert!(regex2.is_hit("/my-path_123/456"));
        assert!(!regex2.is_hit("/"));
        assert!(!regex2.is_hit("#123"));

        let regex3 = MatchPath {
            path: "^/[a-z0-9-.]{2,}/michael".to_string(),
            match_type: MatchType::RegexLookup,
        };
        assert!(regex3.is_hit("/my-path/michael"));
        assert!(!regex3.is_hit("/m/michael"));
        assert!(!regex3.is_hit("/my-path/joe"));
        assert!(!regex3.is_hit("/"));
        assert!(!regex3.is_hit("#123"));

        let regex4 = MatchPath {
            path: "x-gefyra=michael".to_string(),
            match_type: MatchType::RegexLookup,
        };
        assert!(regex4.is_hit("/my-path/?x-gefyra=michael"));
        assert!(!regex4.is_hit("/my-path/?x-gefyra=joe"));
        assert!(!regex4.is_hit("/"));
        assert!(!regex4.is_hit("#123"));
    }

    #[test]
    fn match_header() {
        let m1 = MatchHeader {
            name: "x-gefyra".to_string(),
            value: "michael".to_string(),
            match_type: MatchType::ExactLookup,
        };
        assert!(m1.is_hit("x-gefyra", "michael"));
        assert!(!m1.is_hit("g-gefyra", "michael"));
        assert!(!m1.is_hit("x-gefyra", "michael1"));

        let m2 = MatchHeader {
            name: "x-gefyra".to_string(),
            value: "michael".to_string(),
            match_type: MatchType::PrefixLookup,
        };
        assert!(m2.is_hit("x-gefyra", "michael123"));
        assert!(m2.is_hit("x-gefyra", "michael"));
        assert!(!m2.is_hit("g-gefyra", "michael"));
        assert!(m2.is_hit("x-gefyra", "michael"));
        assert!(!m2.is_hit("x-gefyra123", "michael"));

        let m3 = MatchHeader {
            name: "x-gefyra-[a-z0-9]*".to_string(),
            value: "michael[1-9]{0,2}$".to_string(),
            match_type: MatchType::RegexLookup,
        };
        assert!(m3.is_hit("x-gefyra-from123", "michael"));
        assert!(m3.is_hit("x-gefyra-from123", "michael12"));
        assert!(!m3.is_hit("x-gefyra-from123", "michael123"));
        assert!(m3.is_hit("x-gefyra-", "michael"));
        assert!(!m3.is_hit("g-gefyra", "michael"));
        assert!(!m3.is_hit("x-gefyra", "michael12"));
        assert!(!m3.is_hit("x-gefyra123", "michael"));
    }

    #[test]
    fn match_conditions() {
        let and_cond1 = MatchAndCondition {
            and_match: vec![
                MatchRule::Header(MatchHeader {
                    name: "x-gefyra".to_string(),
                    value: "jon".to_string(),
                    match_type: MatchType::ExactLookup,
                }),
                MatchRule::Path(MatchPath {
                    path: "/my-path_123".to_string(),
                    match_type: MatchType::ExactLookup,
                }),
            ],
        };

        let and_cond2 = MatchAndCondition {
            and_match: vec![MatchRule::Path(MatchPath {
                path: "/always".to_string(),
                match_type: MatchType::ExactLookup,
            })],
        };
        let mut req1 = RequestHeader::build(Method::GET, "/my-path_123".as_bytes(), None).unwrap();
        let mut req2 = RequestHeader::build(Method::GET, "/always".as_bytes(), None).unwrap();
        let mut req3 = RequestHeader::build(Method::GET, "/never".as_bytes(), None).unwrap();
        assert!(!and_cond1.is_hit(&req1));
        assert!(!and_cond1.is_hit(&req2));
        assert!(!and_cond1.is_hit(&req3));
        req1.append_header("x-gefyra", "jon").unwrap();
        req2.append_header("x-gefyra", "jon").unwrap();
        req3.append_header("x-gefyra", "balu").unwrap();
        assert!(and_cond1.is_hit(&req1));
        assert!(!and_cond1.is_hit(&req2));
        assert!(!and_cond1.is_hit(&req3));

        assert!(and_cond2.is_hit(&req2));

        // chain to and-conditions from above with or-operator
        let or_cond1 = MatchOrCondition {
            or_rules: vec![and_cond1, and_cond2],
        };

        assert!(or_cond1.is_hit(&req1));
        assert!(or_cond1.is_hit(&req2));
        assert!(!or_cond1.is_hit(&req3));
    }

    #[test]
    fn read_gefyra_client() {
        let users = " 
        user-1: 
            endpoint: \"www.blueshoe.io:443\" 
            tls: true 
            sni: \"www.blueshoe.io\" 
            rules: 
                - match: 
                    - matchHeader: 
                        name: \"x-gefyra\" 
                        value: \"user-1\"
                    - matchPath: 
                        path: \"/my-svc\"
                        type: \"prefix\"
                - match:
                    - matchPath:
                        path: \"/always\"
                        type: \"prefix\"
        user-2:  
            endpoint: \"www.gefyra.dev:443\"  
            tls: false  
            rules:
                - match:
                    - matchHeader:
                        name: \"x-gefyra\"
                        value: \"user-1\"
                    - matchPath: 
                        path: \"/my-svc\"
                        type: \"prefix\"
                - match:
                    - matchPath:
                        path: \"/always\"
                        type: \"prefix\"
        ";

        let mapping1 = serde_yaml::from_str(users).unwrap();
        let clients = GefyraClient::from_yaml(&mapping1, false, "".to_string());
        assert_eq!(clients.len(), 2);
        assert_eq!(clients[0].key, "user-1");
        assert_eq!(clients[1].key, "user-2");
        assert_eq!(clients[0].peer.is_tls(), true);
        assert_eq!(clients[0].peer.sni(), "www.blueshoe.io");
        assert_eq!(clients[0].matching_rules.or_rules.len(), 2);
    }
}
