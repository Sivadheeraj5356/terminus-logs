namespace cb {
bool wait_event(int fd){ uint64_t v=0; ssize_t n=read(fd,&v,8); return n==8; }
void signal_event(int fd){ uint64_t one=1; (void)write(fd,&one,8); }
}
