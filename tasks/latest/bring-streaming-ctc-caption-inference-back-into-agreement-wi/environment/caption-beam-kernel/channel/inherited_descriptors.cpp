namespace cb {
struct InheritedFds { int mailbox_fd=-1, request_fd=-1, response_fd=-1; };
std::optional<InheritedFds> inherited_descriptors() { const char* m=getenv("CAPTION_MAILBOX_FD"); const char* r=getenv("CAPTION_REQUEST_EVENT_FD"); const char* q=getenv("CAPTION_RESPONSE_EVENT_FD"); if(!m||!r||!q) return std::nullopt; return InheritedFds{std::atoi(m), std::atoi(r), std::atoi(q)}; }
}
