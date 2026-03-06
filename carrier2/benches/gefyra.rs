use carrier2::GefyraClient;
use criterion::{criterion_group, criterion_main, Criterion};
use fixtures::{get_gefyra_clients, get_simple_header};
use pingora::http::RequestHeader;

mod fixtures;

fn select_gefyra_client(gefyra_clients: Vec<GefyraClient>, header: RequestHeader) {
    // this is the heavy duty function from our code
    let pos = gefyra_clients
        .iter()
        .position(|c| c.matching_rules.is_hit(&header));
    if let Some(pos) = pos {
        let _ = &gefyra_clients[pos];
    }
}

fn criterion_benchmark(c: &mut Criterion) {
    let clients_200 = get_gefyra_clients(200);
    let req_20 = get_simple_header(20, "/my-path".to_string());

    c.bench_function("select from 200 gefyra client, 20 header", |b| {
        b.iter(|| select_gefyra_client(clients_200.clone(), req_20.clone()))
    });

    let clients_500 = get_gefyra_clients(200);
    c.bench_function("select from 500 gefyra client, 20 header", |b| {
        b.iter(|| select_gefyra_client(clients_500.clone(), req_20.clone()))
    });

    let req_50 = get_simple_header(20, "/my-path/".to_string());
    c.bench_function("select from 200 gefyra client, 50 header", |b| {
        b.iter(|| select_gefyra_client(clients_200.clone(), req_50.clone()))
    });
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
