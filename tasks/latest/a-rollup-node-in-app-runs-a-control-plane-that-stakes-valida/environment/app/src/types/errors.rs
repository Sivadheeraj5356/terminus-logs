use crate::json::Json;
use crate::server::response::Response;

pub struct ApiError {
    pub status: u16,
    pub code: String,
    pub message: String,
}

impl ApiError {
    pub fn new(status: u16, code: &str, message: &str) -> ApiError {
        ApiError {
            status,
            code: code.to_string(),
            message: message.to_string(),
        }
    }

    pub fn bad_request(message: &str) -> ApiError {
        ApiError::new(400, "invalid_request", message)
    }

    pub fn unauthorized() -> ApiError {
        ApiError::new(401, "unauthorized", "authentication required")
    }

    pub fn forbidden() -> ApiError {
        ApiError::new(403, "forbidden", "operation not permitted")
    }

    pub fn not_found() -> ApiError {
        ApiError::new(404, "not_found", "resource not found")
    }

    pub fn conflict(code: &str, message: &str) -> ApiError {
        ApiError::new(409, code, message)
    }

    pub fn unprocessable(code: &str, message: &str) -> ApiError {
        ApiError::new(422, code, message)
    }

    pub fn to_response(&self) -> Response {
        let mut error = Json::obj();
        error.set("code", Json::Str(self.code.clone()));
        error.set("message", Json::Str(self.message.clone()));
        let mut body = Json::obj();
        body.set("error", error);
        Response::json(self.status, body)
    }
}
