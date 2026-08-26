use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread;

type Job = Box<dyn FnOnce() + Send + 'static>;

pub struct ThreadPool {
    sender: mpsc::Sender<Job>,
}

impl ThreadPool {
    pub fn new(size: usize) -> ThreadPool {
        let (sender, receiver) = mpsc::channel::<Job>();
        let receiver = Arc::new(Mutex::new(receiver));
        for _ in 0..size.max(1) {
            let receiver = Arc::clone(&receiver);
            thread::spawn(move || loop {
                let job = {
                    let guard = receiver.lock().unwrap();
                    guard.recv()
                };
                match job {
                    Ok(job) => job(),
                    Err(_) => break,
                }
            });
        }
        ThreadPool { sender }
    }

    pub fn execute<F>(&self, job: F)
    where
        F: FnOnce() + Send + 'static,
    {
        let _ = self.sender.send(Box::new(job));
    }
}
