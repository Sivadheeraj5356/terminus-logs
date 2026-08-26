package backend

const DefaultResponse = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"

func SuccessResponse() []byte {
	return []byte(DefaultResponse)
}
