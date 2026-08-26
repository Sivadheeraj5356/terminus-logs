#include "tel_db.h"
#include "tel_fd.h"
#include "tel_journal.h"
#include "tel_replay.h"
#include "tel_report.h"
#include "tel_sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static void usage(const char *a){fprintf(stderr,"usage: %s --db PATH --scenario ID --loops N [--state-dir DIR] [--no-resume]\n",a);}
static void pids(FILE *f,const uint64_t *p,size_t n){fputc('[',f);for(size_t i=0;i<n;i++){if(i)fputc(',',f);fprintf(f,"%llu",(unsigned long long)p[i]);}fputc(']',f);}
static int write_json(tel_scenario_report_t *s,const char *outpath){char *body=NULL;size_t n=0;FILE *m=open_memstream(&body,&n);if(!m)return -1;fprintf(m,"{\"affected_pids\":");pids(m,s->affected_pids,s->affected_pids_len);fprintf(m,",\"cache_hit\":%s,\"correlated_triples\":%d,\"errors_seen\":%d,\"fd_delta\":%d,\"final_open_fds\":%d,\"generation\":%llu,\"initial_open_fds\":%d,\"input_fingerprint\":\"%s\",\"journal_bytes\":%llu,\"leak_reproduced\":%s,\"loops_run\":%d,\"recovered_records\":%u,\"restarts_seen\":%d,\"root_cause\":\"%s\",\"samples_scanned\":%d,\"scenario_id\":\"%s\",\"schema_version\":%d}",s->cache_hit?"true":"false",s->correlated_triples,s->errors_seen,s->fd_delta,s->final_open_fds,(unsigned long long)s->generation,s->initial_open_fds,s->input_fingerprint,(unsigned long long)s->journal_bytes,s->leak_reproduced?"true":"false",s->loops_run,s->recovered_records,s->restarts_seen,s->root_cause,s->samples_scanned,s->scenario_id,s->schema_version);if(fclose(m)){free(body);return -1;}tel_sha256_hex(body,n,s->body_sha256);FILE *f=fopen(outpath,"w");if(!f){free(body);return -1;}fprintf(f,"%.*s,\"body_sha256\":\"%s\"}",(int)n-1,body,s->body_sha256);int rc=fclose(f);free(body);return rc? -1:0;}
static int run_one(const char *dbp,const char *sid,int loops,const char *state,int resume,const char *outpath){
 tel_journal_t j; char fp[65]; tel_scenario_report_t rep; memset(&rep,0,sizeof rep);strncpy(rep.scenario_id,sid,63);rep.schema_version=2;rep.loops_run=loops;strcpy(rep.root_cause,"none");
 if(tel_journal_fingerprint(dbp,sid,loops,fp)||tel_journal_open(&j,state,sid)) return 2;
 int hit=0;
 if(resume&&tel_journal_load(&j,fp,&rep,&hit)){tel_journal_close(&j);return 2;}
 rep.cache_hit=hit;
 strcpy(rep.input_fingerprint,fp);
 if(!hit){tel_env_t db;if(tel_env_open(dbp,&db)){tel_journal_close(&j);return 2;}rep.initial_open_fds=tel_count_open_fds();tel_replay_stats_t st;if(tel_replay_scenario(&db,sid,loops,&st)){tel_env_close(&db);tel_journal_close(&j);return 2;}rep.final_open_fds=tel_count_open_fds();rep.fd_delta=rep.final_open_fds-rep.initial_open_fds;rep.leak_reproduced=rep.fd_delta>0;strncpy(rep.root_cause,rep.leak_reproduced?st.leak_phase:"none",31);rep.samples_scanned=st.samples_scanned;rep.errors_seen=st.errors_seen;rep.restarts_seen=st.restarts_seen;rep.correlated_triples=st.correlated_triples;rep.affected_pids=st.affected_pids;rep.affected_pids_len=st.affected_pids_len;st.affected_pids=NULL;rep.generation=j.last_generation+1;rep.recovered_records=j.recovered_records;if(tel_journal_append(&j,fp,&rep)){free(rep.affected_pids);tel_env_close(&db);tel_journal_close(&j);return 2;}tel_env_close(&db);}else{rep.initial_open_fds=tel_count_open_fds();rep.final_open_fds=rep.initial_open_fds;rep.fd_delta=0;rep.leak_reproduced=0;}
 int rc=write_json(&rep,outpath);free(rep.affected_pids);tel_journal_close(&j);return rc?2:0;}
int tel_cli_run(int argc,char **argv){const char *db=NULL,*sid=NULL,*state="/app/state",*outpath="/app/output/.single_report.json";int loops=0,resume=1;for(int i=1;i<argc;i++){if(!strcmp(argv[i],"--db")&&i+1<argc)db=argv[++i];else if(!strcmp(argv[i],"--scenario")&&i+1<argc)sid=argv[++i];else if(!strcmp(argv[i],"--loops")&&i+1<argc)loops=atoi(argv[++i]);else if(!strcmp(argv[i],"--state-dir")&&i+1<argc)state=argv[++i];else if(!strcmp(argv[i],"--output")&&i+1<argc)outpath=argv[++i];else if(!strcmp(argv[i],"--no-resume"))resume=0;else{usage(argv[0]);return 2;}}if(!db||!sid||loops<=0){usage(argv[0]);return 2;}mkdir("/app/output",0755);return run_one(db,sid,loops,state,resume,outpath);}
