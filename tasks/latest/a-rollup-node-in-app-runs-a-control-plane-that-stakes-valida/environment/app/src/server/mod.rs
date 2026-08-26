pub mod http;
pub mod request;
pub mod response;
pub mod threadpool;

use request::Request;
use response::Response;
use std::io::Write;
use std::net::TcpListener;
use std::sync::Arc;
use threadpool::ThreadPool;

pub fn serve<F>(addr: &str, threads: usize, dispatch: F)
where
    F: Fn(Request) -> Response + Send + Sync + 'static,
{
    let listener = TcpListener::bind(addr).expect("bind failed");
    let dispatch = Arc::new(dispatch);
    let pool = ThreadPool::new(threads);
    for stream in listener.incoming() {
        let stream = match stream {
            Ok(s) => s,
            Err(_) => continue,
        };
        let dispatch = Arc::clone(&dispatch);
        pool.execute(move || {
            let mut stream = stream;
            match http::read_request(&mut stream) {
                Ok(request) => {
                    let response = dispatch(request);
                    let _ = stream.write_all(&response.encode());
                    let _ = stream.flush();
                }
                Err(_) => {
                    let response = Response::text(400, "bad request");
                    let _ = stream.write_all(&response.encode());
                }
            }
        });
    }
}
