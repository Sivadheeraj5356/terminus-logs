create table checkpoint (
  partition_id text primary key,
  sequence integer not null,
  status text not null,
  cursor_start text not null,
  cursor_end text not null,
  prev_cursor text not null,
  digest_hex text not null,
  omission_reason text,
  omission_digest_hex text,
  service_generation text not null,
  batch_id text not null,
  terminal integer not null
);
insert into checkpoint values ('part-0001',1,'export','s=0;b=boot-a','s=8;b=boot-a','','b9b20dc433b681eb0750cc75912139d0557992ac9124cd418497441927f0c37f','','','gen-42/reload-1','batch-20260714',1);
insert into checkpoint values ('part-0002',2,'export','s=9;b=boot-a','s=17;b=boot-a','s=8;b=boot-a','5fa0d2d1697f7d694fead3f767e522720a072d7c69ccc982cc16ca2c35131e72','','','gen-42/reload-1','batch-20260714',1);
insert into checkpoint values ('part-0003',4,'export','s=18;b=boot-b','s=25;b=boot-b','s=17;b=boot-a','f0803159ce3e380fe0bc8c74f5fced935aa0be9d0eee81b86afc589bd52db8f5','','','gen-42/reload-1','batch-20260714',1);
