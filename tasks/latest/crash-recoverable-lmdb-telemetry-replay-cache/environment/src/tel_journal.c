#include "tel_journal.h"
#include "tel_crc32c.h"
#include "tel_sha256.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define JMAGIC 0x54454c4aU
#define JVERSION 2U
#define MAX_PIDS 1000000U
#pragma pack(push,1)
typedef struct {
    uint32_t magic, version, record_len, pid_count;
    uint64_t generation;
    char fingerprint[65];
    int32_t loops_run, samples_scanned, errors_seen, restarts_seen, correlated_triples;
    char scenario_id[64];
} rec_hdr_t;
#pragma pack(pop)

static int mkdir_p(const char *p){ if(mkdir(p,0755)==0||errno==EEXIST)return 0; return -1; }
static int read_all(int fd, void *buf, size_t n){ size_t o=0; while(o<n){ssize_t r=read(fd,(char*)buf+o,n-o); if(r==0)return 1; if(r<0){if(errno==EINTR)continue;return -1;} o+=(size_t)r;} return 0; }
static int write_all(int fd,const void *buf,size_t n){size_t o=0;while(o<n){ssize_t w=write(fd,(const char*)buf+o,n-o);if(w<0){if(errno==EINTR)continue;return -1;}o+=(size_t)w;}return 0;}
static int slurp(const char *path,unsigned char **out,size_t *len){FILE *f=fopen(path,"rb"); if(!f)return -1; if(fseek(f,0,SEEK_END)||((*len=(size_t)ftell(f)),fseek(f,0,SEEK_SET))){fclose(f);return -1;} *out=malloc(*len?*len:1); if(!*out){fclose(f);return -1;} if(*len&&fread(*out,1,*len,f)!=*len){free(*out);fclose(f);return -1;} fclose(f);return 0;}
int tel_journal_fingerprint(const char *db_path,const char *sid,int loops,char out[65]){
    char data[768]; snprintf(data,sizeof(data),"%s/data.mdb",db_path);
    unsigned char *a=NULL,*b=NULL; size_t an=0,bn=0;
    struct stat st; if(stat(data,&st)) return -1; an=sizeof(st.st_size); a=malloc(an); memcpy(a,&st.st_size,an); b=(unsigned char*)strdup(""); bn=0;
    size_t sn=strlen(sid), total=an+bn+sn+sizeof(loops); unsigned char *buf=malloc(total?total:1); if(!buf){free(a);free(b);return -1;}
    size_t o=0; memcpy(buf+o,a,an);o+=an;memcpy(buf+o,b,bn);o+=bn;memcpy(buf+o,sid,sn);o+=sn;memcpy(buf+o,&loops,sizeof loops);o+=sizeof loops;
    tel_sha256_hex(buf,o,out); free(buf);free(a);free(b);return 0;
}
int tel_journal_open(tel_journal_t *j,const char *dir,const char *sid){memset(j,0,sizeof(*j));j->lock_fd=-1;if(mkdir_p(dir))return -1;char lockp[512];snprintf(j->path,sizeof(j->path),"%s/%s.journal",dir,sid);snprintf(lockp,sizeof(lockp),"%s/%s.lock",dir,sid);j->lock_fd=open(lockp,O_CREAT|O_RDWR,0644);if(j->lock_fd<0)return -1;return 0;}
void tel_journal_close(tel_journal_t *j){if(j->lock_fd>=0){close(j->lock_fd);j->lock_fd=-1;}}
static void clear_dynamic(tel_scenario_report_t *r){free(r->affected_pids);r->affected_pids=NULL;r->affected_pids_len=0;}
int tel_journal_load(tel_journal_t *j,const char fp[65],tel_scenario_report_t *out,int *hit){
    *hit=0; int fd=open(j->path,O_RDWR|O_CREAT,0644); if(fd<0)return -1; off_t good=0; rec_hdr_t latest={0}; uint64_t *latest_pids=NULL;
    for(;;){rec_hdr_t h; int rr=read_all(fd,&h,sizeof h); if(rr==1)break; if(rr<0)goto fail; if(h.magic!=JMAGIC||h.version!=JVERSION||h.pid_count>MAX_PIDS||h.record_len!=sizeof(h)+h.pid_count*8+4){j->had_corrupt_tail=1;break;} size_t pn=(size_t)h.pid_count*8; uint64_t *p=malloc(pn?pn:1); uint32_t stored=0; unsigned char *crcbuf=malloc(sizeof h+pn); if(!p||!crcbuf){free(p);free(crcbuf);goto fail;} if(read_all(fd,p,pn)||read_all(fd,&stored,4)){free(p);free(crcbuf);j->had_corrupt_tail=1;break;} memcpy(crcbuf,&h,sizeof h);memcpy(crcbuf+sizeof h,p,pn);uint32_t calc=tel_crc32c(crcbuf,sizeof h+pn);free(crcbuf);if(calc!=stored){free(p);j->had_corrupt_tail=1;break;} good+=h.record_len;j->valid_records++;j->last_generation=h.generation;free(latest_pids);latest=h;latest_pids=p;
    }
    if(j->had_corrupt_tail){goto fail;}
    struct stat st;if(fstat(fd,&st)==0)out->journal_bytes=(uint64_t)st.st_size;close(fd);
    if(latest.generation&&strcmp(latest.fingerprint,fp)==0){clear_dynamic(out);strncpy(out->scenario_id,latest.scenario_id,sizeof(out->scenario_id)-1);out->loops_run=latest.loops_run;out->samples_scanned=latest.samples_scanned;out->errors_seen=latest.errors_seen;out->restarts_seen=latest.restarts_seen;out->correlated_triples=latest.correlated_triples;out->affected_pids=latest_pids;out->affected_pids_len=latest.pid_count;out->generation=latest.generation;out->recovered_records=j->recovered_records;strcpy(out->input_fingerprint,fp);*hit=1;return 0;}free(latest_pids);return 0;
fail: close(fd);free(latest_pids);return -1;
}
int tel_journal_append(tel_journal_t *j,const char fp[65],const tel_scenario_report_t *r){
    rec_hdr_t h={0};h.magic=JMAGIC;h.version=JVERSION;h.pid_count=(uint32_t)r->affected_pids_len;h.record_len=(uint32_t)(sizeof h+r->affected_pids_len*8+4);h.generation=r->generation;strncpy(h.fingerprint,fp,64);h.fingerprint[64]=0;h.loops_run=r->loops_run;h.samples_scanned=r->samples_scanned;h.errors_seen=r->errors_seen;h.restarts_seen=r->restarts_seen;h.correlated_triples=r->correlated_triples;strncpy(h.scenario_id,r->scenario_id,63);
    size_t pn=r->affected_pids_len*8, cn=sizeof h+pn;unsigned char *buf=malloc(cn);if(!buf)return -1;memcpy(buf,&h,sizeof h);memcpy(buf+sizeof h,r->affected_pids,pn);uint32_t crc=tel_crc32c(buf,cn);int fd=open(j->path,O_WRONLY|O_CREAT|O_APPEND,0644);if(fd<0){free(buf);return -1;}int rc=write_all(fd,buf,cn)||write_all(fd,&crc,4);struct stat st;if(!fstat(fd,&st))((tel_scenario_report_t*)r)->journal_bytes=(uint64_t)st.st_size;close(fd);free(buf);return rc?-1:0;
}
int tel_journal_compact(tel_journal_t *j){(void)j;return 0;}
