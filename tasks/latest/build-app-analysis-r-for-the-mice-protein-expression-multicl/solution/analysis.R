TASK_NAME <- "mice-protein-missing-multi-class"
TASK_KIND <- "multiclass"
TARGET <- "class"
POS <- ""
NEG <- ""
FN <- 1
FP <- 1
PROT <- ""
NUMS <- c("dyrk1a_n", "itsn1_n", "bdnf_n", "nr1_n", "nr2a_n", "pakt_n", "pbraf_n", "pcamkii_n", "pcreb_n", "pelk_n", "perk_n", "pjnk_n", "pkca_n", "pmek_n", "pnr1_n", "pnr2a_n", "pnr2b_n", "ppkcab_n", "prsk_n", "akt_n", "braf_n", "camkii_n", "creb_n", "elk_n", "erk_n", "gsk3b_n", "jnk_n", "mek_n", "trka_n", "rsk_n", "app_n", "bcatenin_n", "sod1_n", "mtor_n", "p38_n", "pmtor_n", "dscr1_n", "ampka_n", "nr2b_n", "pnumb_n", "raptor_n", "tiam1_n", "pp70s6_n", "numb_n", "p70s6_n", "pgsk3b_n", "ppkcg_n", "cdk5_n", "s6_n", "adarb1_n", "acetylh3k9_n", "rrp1_n", "bax_n", "arc_n", "erbb4_n", "nnos_n", "tau_n", "gfap_n", "glur3_n", "glur4_n", "il1b_n", "p3525_n", "pcasp9_n", "psd95_n", "snca_n", "ubiquitin_n", "pgsk3b_tyr216_n", "shh_n", "ps6_n", "syp_n", "cana_n", "bad_n", "bcl2_n", "pcfos_n", "h3ack18_n", "egr1_n", "h3mek4_n")
CATS <- c("genotype", "treatment", "behavior")
CLASSES <- c("c-CS-m", "c-CS-s", "c-SC-m", "c-SC-s", "t-CS-m", "t-CS-s", "t-SC-m", "t-SC-s")
LAM <- c(0.001,0.01,0.1,1,10)
PROTEIN_PAIRS <- list(
  pair_01=c("dyrk1a_n", "itsn1_n"),
  pair_02=c("bdnf_n", "nr1_n"),
  pair_03=c("nr2a_n", "pakt_n"),
  pair_04=c("pbraf_n", "pcamkii_n"),
  pair_05=c("pcreb_n", "pelk_n"),
  pair_06=c("perk_n", "pjnk_n"),
  pair_07=c("pkca_n", "pmek_n"),
  pair_08=c("pnr1_n", "pnr2a_n")
)
OUT <- Sys.getenv("OUTPUT_DIR","/app/outputs")
dir.create(OUT,showWarnings=FALSE,recursive=TRUE)
q <- function(x) paste0("\"",gsub("\"","\\\"",as.character(x)),"\"")
jv <- function(x) { if(length(x)==0) return("[]"); if(length(x)>1) return(paste0("[",paste(vapply(x,jv,character(1)),collapse=", "),"]")); if(is.numeric(x)) return(ifelse(is.na(x),"null",sprintf("%.12g",x))); q(x) }
wj <- function(v,p) { z<-character(0); for(n in names(v)) z<-c(z,paste0(q(n),": ",jv(v[[n]]))); writeLines(paste0("{
  ",paste(z,collapse=",
  "),"
}"),p) }
safe <- function(x) { y<-tolower(gsub("[^0-9A-Za-z]+","_",as.character(x))); y<-gsub("^_+|_+$","",y); ifelse(y=="","value",ifelse(grepl("^[0-9]",y),paste0("x_",y),y)) }
cc <- function(x) { y<-as.character(x); y[is.na(y)|y==""|y=="?"|tolower(y)=="nan"]<-"missing"; y }
learn <- function(d) { f<-d[d$split_role=="fit",,drop=FALSE]; m<-list(); s<-list(); lv<-list(); for(c in NUMS) { v<-suppressWarnings(as.numeric(f[[c]])); mu<-mean(v,na.rm=TRUE); if(is.na(mu)) mu<-0; v[is.na(v)]<-mu; sdv<-stats::sd(v); if(is.na(sdv)||sdv==0) sdv<-1; m[[c]]<-mu; s[[c]]<-sdv }; for(c in CATS) lv[[c]]<-sort(unique(cc(f[[c]]))); list(m=m,s=s,lv=lv) }
mx <- function(d,o) { cols<-list(rep(1,nrow(d))); nm<-c("intercept"); for(c in NUMS) { v<-suppressWarnings(as.numeric(d[[c]])); v[is.na(v)]<-o$m[[c]]; cols[[length(cols)+1]]<-(v-o$m[[c]])/o$s[[c]]; nm<-c(nm,c) }; for(c in CATS) { v<-cc(d[[c]]); for(a in o$lv[[c]]) { cols[[length(cols)+1]]<-as.numeric(v==a); nm<-c(nm,paste0(c,"__",safe(a))) } }; x<-do.call(cbind,cols); colnames(x)<-nm; x }
ridge <- function(x,y,l) { p<-diag(ncol(x)); p[1,1]<-0; solve(t(x)%*%x+l*p,t(x)%*%y) }
sg <- function(x) 1/(1+exp(-pmax(pmin(x,35),-35)))
sm <- function(x) { y<-x-apply(x,1,max); e<-exp(y); e/rowSums(e) }
ba <- function(a,p,cls) mean(vapply(cls,function(c) if(sum(a==c)>0) mean(p[a==c]==c) else NA_real_,numeric(1)),na.rm=TRUE)
mf <- function(a,p,cls) mean(vapply(cls,function(c) { tp<-sum(a==c&p==c); fp<-sum(a!=c&p==c); fn<-sum(a==c&p!=c); pr<-ifelse(tp+fp==0,0,tp/(tp+fp)); rc<-ifelse(tp+fn==0,0,tp/(tp+fn)); ifelse(pr+rc==0,0,2*pr*rc/(pr+rc)) },numeric(1)))
auc <- function(y,p) { np<-sum(y==1); nn<-sum(y==0); if(np==0||nn==0) return(NA_real_); r<-rank(p,ties.method="average"); (sum(r[y==1])-np*(np+1)/2)/(np*nn) }
llb <- function(y,p) { p<-pmin(pmax(p,1e-9),1-1e-9); -mean(y*log(p)+(1-y)*log(1-p)) }
llm <- function(i,p) -mean(log(pmax(p[cbind(seq_along(i),i)],1e-9)))
stability_refits <- function(f) {
  probability_names <- paste0("proba_", safe(CLASSES))
  prediction_parts <- list()
  report_parts <- list()
  for (repeat_id in 1:4) {
    internal_validation_mask <- as.integer(f$row_id) %% 4L == repeat_id - 1L
    internal_fit <- f[!internal_validation_mask, , drop=FALSE]
    internal_validation <- f[internal_validation_mask, , drop=FALSE]
    internal_fit$split_role <- "fit"
    prep <- learn(internal_fit)
    x_fit <- mx(internal_fit, prep)
    x_validation <- mx(internal_validation, prep)
    y_fit_index <- match(as.character(internal_fit[[TARGET]]), CLASSES)
    y_validation_index <- match(as.character(internal_validation[[TARGET]]), CLASSES)
    y_fit <- matrix(0, nrow(internal_fit), length(CLASSES))
    for (i in seq_along(y_fit_index)) y_fit[i, y_fit_index[[i]]] <- 1
    scores <- data.frame()
    models <- list()
    for (lambda in LAM) {
      beta <- ridge(x_fit, y_fit, lambda)
      models[[as.character(lambda)]] <- beta
      probability <- sm(x_validation %*% beta)
      scores <- rbind(scores, data.frame(lambda=lambda, validation_log_loss=llm(y_validation_index, probability)))
    }
    best <- scores[order(scores$validation_log_loss, scores$lambda), ][1, ]
    probability <- sm(x_validation %*% models[[as.character(best$lambda)]])
    predicted <- CLASSES[max.col(probability, ties.method="first")]
    prediction_frame <- data.frame(
      repeat_id=repeat_id,
      row_id=internal_validation$row_id,
      actual=as.character(internal_validation[[TARGET]]),
      predicted=predicted,
      stringsAsFactors=FALSE
    )
    for (i in seq_along(probability_names)) prediction_frame[[probability_names[[i]]]] <- probability[, i]
    prediction_frame$split_role <- "stability_validation"
    prediction_parts[[repeat_id]] <- prediction_frame
    report_parts[[repeat_id]] <- data.frame(
      repeat_id=repeat_id,
      n_fit=nrow(internal_fit),
      n_validation=nrow(internal_validation),
      selected_lambda=best$lambda,
      validation_log_loss=best$validation_log_loss,
      validation_macro_f1=mf(as.character(internal_validation[[TARGET]]), predicted, CLASSES),
      mean_confidence=mean(apply(probability, 1, max))
    )
  }
  predictions <- do.call(rbind, prediction_parts)
  predictions <- predictions[order(predictions$repeat_id, predictions$row_id), ]
  report <- do.call(rbind, report_parts)
  report <- report[order(report$repeat_id), ]
  list(predictions=predictions, report=report)
}
boundary_refit_report <- function(f, te, prep, selected_lambda, base_prob, base_pred) {
  x_fit <- mx(f, prep)
  x_test <- mx(te, prep)
  feature_columns <- seq_len(ncol(x_fit))[-1]
  margins <- apply(base_prob, 1, function(row) {
    ordered <- sort(row, decreasing=TRUE)
    ordered[[1]] - ordered[[2]]
  })
  audit_positions <- order(margins, as.numeric(te$row_id))[seq_len(min(10, nrow(te)))]
  rows <- list()
  for (rank in seq_along(audit_positions)) {
    test_pos <- audit_positions[[rank]]
    predicted_label <- base_pred[[test_pos]]
    candidates <- which(as.character(f[[TARGET]]) != predicted_label)
    delta <- sweep(x_fit[candidates, feature_columns, drop=FALSE], 2, x_test[test_pos, feature_columns], "-")
    distances <- sqrt(rowSums(delta^2))
    nearest <- candidates[order(distances, as.numeric(f$row_id[candidates]))[[1]]]
    reduced_fit <- f[-nearest, , drop=FALSE]
    reduced_fit$split_role <- "fit"
    reduced_prep <- learn(reduced_fit)
    reduced_x <- mx(reduced_fit, reduced_prep)
    test_x <- mx(te[test_pos, , drop=FALSE], reduced_prep)
    reduced_index <- match(as.character(reduced_fit[[TARGET]]), CLASSES)
    reduced_y <- matrix(0, nrow(reduced_fit), length(CLASSES))
    for (i in seq_along(reduced_index)) reduced_y[i, reduced_index[[i]]] <- 1
    beta <- ridge(reduced_x, reduced_y, selected_lambda)
    refit_prob <- sm(test_x %*% beta)
    refit_pred <- CLASSES[which.max(refit_prob[1, ])]
    base_ordered <- sort(base_prob[test_pos, ], decreasing=TRUE)
    refit_ordered <- sort(refit_prob[1, ], decreasing=TRUE)
    rows[[rank]] <- data.frame(
      audit_rank=rank,
      row_id=te$row_id[[test_pos]],
      actual=as.character(te[[TARGET]])[[test_pos]],
      baseline_predicted=predicted_label,
      refit_predicted=refit_pred,
      removed_row_id=f$row_id[[nearest]],
      removed_label=as.character(f[[TARGET]])[[nearest]],
      nearest_distance=distances[order(distances, as.numeric(f$row_id[candidates]))[[1]]],
      baseline_margin=base_ordered[[1]] - base_ordered[[2]],
      refit_margin=refit_ordered[[1]] - refit_ordered[[2]],
      probability_l1_shift=sum(abs(refit_prob[1, ] - base_prob[test_pos, ])),
      decision_changed=as.integer(refit_pred != predicted_label),
      stringsAsFactors=FALSE
    )
  }
  do.call(rbind, rows)
}
paired_boundary_reselection_report <- function(f, v, te, prep, base_prob, base_pred) {
  x_fit <- mx(f, prep)
  x_test <- mx(te, prep)
  feature_columns <- seq_len(ncol(x_fit))[-1]
  margins <- apply(base_prob, 1, function(row) {
    ordered <- sort(row, decreasing=TRUE)
    ordered[[1]] - ordered[[2]]
  })
  audit_positions <- order(margins, as.numeric(te$row_id))[seq_len(min(10, nrow(te)))]
  validation_index <- match(as.character(v[[TARGET]]), CLASSES)
  rows <- list()
  for (rank in seq_along(audit_positions)) {
    test_pos <- audit_positions[[rank]]
    predicted_label <- base_pred[[test_pos]]
    conflict_candidates <- which(as.character(f[[TARGET]]) != predicted_label)
    conflict_delta <- sweep(x_fit[conflict_candidates, feature_columns, drop=FALSE], 2, x_test[test_pos, feature_columns], "-")
    conflict_distances <- sqrt(rowSums(conflict_delta^2))
    conflict_local <- order(conflict_distances, as.numeric(f$row_id[conflict_candidates]))[[1]]
    conflict_nearest <- conflict_candidates[[conflict_local]]
    support_candidates <- which(as.character(f[[TARGET]]) == predicted_label)
    support_delta <- sweep(x_fit[support_candidates, feature_columns, drop=FALSE], 2, x_test[test_pos, feature_columns], "-")
    support_distances <- sqrt(rowSums(support_delta^2))
    support_local <- order(support_distances, as.numeric(f$row_id[support_candidates]))[[1]]
    support_nearest <- support_candidates[[support_local]]
    reduced_fit <- f[-sort(unique(c(conflict_nearest, support_nearest))), , drop=FALSE]
    reduced_fit$split_role <- "fit"
    reduced_prep <- learn(reduced_fit)
    reduced_x <- mx(reduced_fit, reduced_prep)
    validation_x <- mx(v, reduced_prep)
    test_x <- mx(te[test_pos, , drop=FALSE], reduced_prep)
    reduced_index <- match(as.character(reduced_fit[[TARGET]]), CLASSES)
    reduced_y <- matrix(0, nrow(reduced_fit), length(CLASSES))
    for (i in seq_along(reduced_index)) reduced_y[i, reduced_index[[i]]] <- 1
    scores <- data.frame()
    models <- list()
    for (lambda in LAM) {
      beta <- ridge(reduced_x, reduced_y, lambda)
      models[[as.character(lambda)]] <- beta
      probability <- sm(validation_x %*% beta)
      scores <- rbind(scores, data.frame(lambda=lambda, validation_log_loss=llm(validation_index, probability)))
    }
    best <- scores[order(scores$validation_log_loss, scores$lambda), ][1, ]
    local_prob <- sm(test_x %*% models[[as.character(best$lambda)]])
    local_pred <- CLASSES[which.max(local_prob[1, ])]
    base_ordered <- sort(base_prob[test_pos, ], decreasing=TRUE)
    local_ordered <- sort(local_prob[1, ], decreasing=TRUE)
    rows[[rank]] <- data.frame(
      audit_rank=rank,
      row_id=te$row_id[[test_pos]],
      actual=as.character(te[[TARGET]])[[test_pos]],
      baseline_predicted=predicted_label,
      local_refit_predicted=local_pred,
      conflict_removed_row_id=f$row_id[[conflict_nearest]],
      conflict_removed_label=as.character(f[[TARGET]])[[conflict_nearest]],
      support_removed_row_id=f$row_id[[support_nearest]],
      support_removed_label=as.character(f[[TARGET]])[[support_nearest]],
      conflict_distance=conflict_distances[[conflict_local]],
      support_distance=support_distances[[support_local]],
      baseline_margin=base_ordered[[1]] - base_ordered[[2]],
      local_selected_lambda=best$lambda,
      local_validation_log_loss=best$validation_log_loss,
      local_margin=local_ordered[[1]] - local_ordered[[2]],
      probability_l1_shift=sum(abs(local_prob[1, ] - base_prob[test_pos, ])),
      decision_changed=as.integer(local_pred != predicted_label),
      stringsAsFactors=FALSE
    )
  }
  do.call(rbind, rows)
}
d<-read.csv("/app/data/train.csv",stringsAsFactors=FALSE,check.names=FALSE); o<-learn(d); f<-d[d$split_role=="fit",,drop=FALSE]; v<-d[d$split_role=="validation",,drop=FALSE]; te<-d[d$split_role=="test",,drop=FALSE]; xf<-mx(f,o); xv<-mx(v,o); xt<-mx(te,o); terms<-colnames(xf)
if(TASK_KIND=="regression") { yf<-as.numeric(f[[TARGET]]); yv<-as.numeric(v[[TARGET]]); yt<-as.numeric(te[[TARGET]]); val<-data.frame(); mods<-list(); for(l in LAM) { b<-ridge(xf,yf,l); mods[[as.character(l)]]<-b; pv<-as.vector(xv%*%b); val<-rbind(val,data.frame(lambda=l,validation_rmse=sqrt(mean((yv-pv)^2)),validation_mae=mean(abs(yv-pv)))) }; bi<-order(val$validation_rmse,val$lambda)[1]; sl<-val$lambda[bi]; b<-mods[[as.character(sl)]]; pr<-as.vector(xt%*%b); rs<-yt-pr; pred<-data.frame(row_id=te$row_id,actual=yt,predicted=pr,residual=rs,absolute_error=abs(rs),squared_error=rs^2,split_role=te$split_role); pred<-pred[order(pred$row_id),]; met<-list(rmse=sqrt(mean(rs^2)),mae=mean(abs(rs)),r2=1-sum(rs^2)/sum((yt-mean(yt))^2),residual_bias=mean(rs),selected_lambda=sl,validation_rmse=val$validation_rmse[bi],n_fit=nrow(f),n_validation=nrow(v),n_test=nrow(te)); diag<-data.frame(term=terms,coefficient=as.vector(b),abs_coefficient=abs(as.vector(b))); diag<-diag[order(-diag$abs_coefficient,diag$term),]; rb<-data.frame(); srt<-pred[order(pred$predicted,pred$row_id),]; bins<-ceiling(seq_len(nrow(srt))*10/nrow(srt)); for(k in sort(unique(bins))) { z<-srt[bins==k,]; rb<-rbind(rb,data.frame(bin_id=k,n=nrow(z),mean_prediction=mean(z$predicted),mean_actual=mean(z$actual),mean_residual=mean(z$residual),rmse=sqrt(mean(z$residual^2)))) }; wj(met,file.path(OUT,"metrics.json")); write.csv(pred,file.path(OUT,"predictions.csv"),row.names=FALSE,quote=FALSE); write.csv(diag,file.path(OUT,"diagnostics.csv"),row.names=FALSE,quote=FALSE); write.csv(rb,file.path(OUT,"residual_report.csv"),row.names=FALSE,quote=FALSE); write.csv(val,file.path(OUT,"validation_report.csv"),row.names=FALSE,quote=FALSE); wj(list(task_name=TASK_NAME,model_family="ridge_linear",target_column=TARGET,feature_columns=c(NUMS,CATS),numeric_features=NUMS,categorical_features=CATS,selected_lambda=sl,split_source="split_role",preprocessing_source="fit_rows_only"),file.path(OUT,"model_manifest.json")) } else if(TASK_KIND=="binary") { yf<-as.numeric(as.character(f[[TARGET]])==POS); yv<-as.numeric(as.character(v[[TARGET]])==POS); yt<-as.numeric(as.character(te[[TARGET]])==POS); val<-data.frame(); mods<-list(); for(l in LAM) { b<-ridge(xf,yf,l); mods[[as.character(l)]]<-b; val<-rbind(val,data.frame(lambda=l,validation_log_loss=llb(yv,sg(as.vector(xv%*%b))))) }; bi<-order(val$validation_log_loss,val$lambda)[1]; sl<-val$lambda[bi]; b<-mods[[as.character(sl)]]; pv<-sg(as.vector(xv%*%b)); pt<-sg(as.vector(xt%*%b)); tr<-data.frame(); for(th in seq(.05,.95,.05)) { pp<-as.numeric(pv>=th); tr<-rbind(tr,data.frame(threshold=th,false_positive=sum(pp==1&yv==0),false_negative=sum(pp==0&yv==1),expected_cost=(FN*sum(pp==0&yv==1)+FP*sum(pp==1&yv==0))/length(yv),split_role="validation")) }; th<-tr[order(tr$expected_cost,tr$threshold),][1,"threshold"]; pr<-ifelse(pt>=th,POS,NEG); ac<-as.character(te[[TARGET]]); pred<-data.frame(row_id=te$row_id,actual=ac,predicted=pr,probability_positive=pt,expected_cost_negative=pt*FN,expected_cost_positive=(1-pt)*FP,split_role=te$split_role); pred<-pred[order(pred$row_id),]; met<-list(accuracy=mean(ac==pr),balanced_accuracy=ba(ac,pr,CLASSES),roc_auc=auc(yt,pt),brier_score=mean((pt-yt)^2),expected_cost=(FN*sum(pr==NEG&ac==POS)+FP*sum(pr==POS&ac==NEG))/length(ac),selected_lambda=sl,threshold=th,n_fit=nrow(f),n_validation=nrow(v),n_test=nrow(te),false_negative_cost=FN,false_positive_cost=FP); cf<-data.frame(term=terms,coefficient=as.vector(b),abs_coefficient=abs(as.vector(b))); cf<-cf[order(-cf$abs_coefficient,cf$term),]; cal<-data.frame(); ord<-order(pt,te$row_id); bins<-ceiling(seq_along(pt)*10/length(pt)); for(k in sort(unique(bins))) { ix<-which(bins==k); p2<-pt[ord][ix]; y2<-yt[ord][ix]; cal<-rbind(cal,data.frame(bin_id=k,n=length(ix),min_probability=min(p2),max_probability=max(p2),mean_probability=mean(p2),observed_positive_rate=mean(y2),absolute_calibration_error=abs(mean(y2)-mean(p2)))) }; wj(met,file.path(OUT,"metrics.json")); write.csv(pred,file.path(OUT,"predictions.csv"),row.names=FALSE,quote=FALSE); write.csv(tr,file.path(OUT,"threshold_report.csv"),row.names=FALSE,quote=FALSE); write.csv(cal,file.path(OUT,"calibration_report.csv"),row.names=FALSE,quote=FALSE); write.csv(cf,file.path(OUT,"coefficient_report.csv"),row.names=FALSE,quote=FALSE); if(PROT!="") { sub<-data.frame(); g<-sort(unique(cc(te[[PROT]]))); for(gr in g) { ix<-cc(te[[PROT]])==gr; a<-ac[ix]; p<-pr[ix]; sub<-rbind(sub,data.frame(group=gr,n=sum(ix),predicted_positive_rate=mean(p==POS),observed_positive_rate=mean(yt[ix]),false_negative_rate=ifelse(sum(a==POS)==0,0,sum(a==POS&p==NEG)/sum(a==POS)),false_positive_rate=ifelse(sum(a==NEG)==0,0,sum(a==NEG&p==POS)/sum(a==NEG)),balanced_accuracy=ba(a,p,CLASSES))) }; write.csv(sub,file.path(OUT,"subgroup_report.csv"),row.names=FALSE,quote=FALSE) }; wj(list(task_name=TASK_NAME,model_family="ridge_sigmoid",target_column=TARGET,positive_class=POS,negative_class=NEG,feature_columns=c(NUMS,CATS),numeric_features=NUMS,categorical_features=CATS,selected_lambda=sl,split_source="split_role",preprocessing_source="fit_rows_only"),file.path(OUT,"model_manifest.json")) } else { yf<-match(as.character(f[[TARGET]]),CLASSES); yv<-match(as.character(v[[TARGET]]),CLASSES); yt<-match(as.character(te[[TARGET]]),CLASSES); Y<-matrix(0,nrow(f),length(CLASSES)); for(i in seq_along(yf)) Y[i,yf[i]]<-1; val<-data.frame(); mods<-list(); for(l in LAM) { b<-ridge(xf,Y,l); mods[[as.character(l)]]<-b; val<-rbind(val,data.frame(lambda=l,validation_log_loss=llm(yv,sm(xv%*%b)))) }; bi<-order(val$validation_log_loss,val$lambda)[1]; sl<-val$lambda[bi]; b<-mods[[as.character(sl)]]; prob<-sm(xt%*%b); pi<-max.col(prob,ties.method="first"); pr<-CLASSES[pi]; ac<-as.character(te[[TARGET]]); pc<-paste0("proba_",safe(CLASSES)); pred<-data.frame(row_id=te$row_id,actual=ac,predicted=pr); for(i in seq_along(pc)) pred[[pc[i]]]<-prob[,i]; pred$split_role<-te$split_role; pred<-pred[order(pred$row_id),]; cr<-data.frame(); for(cl in CLASSES) { tp<-sum(ac==cl&pr==cl); fp<-sum(ac!=cl&pr==cl); fn<-sum(ac==cl&pr!=cl); pp<-ifelse(tp+fp==0,0,tp/(tp+fp)); rr<-ifelse(tp+fn==0,0,tp/(tp+fn)); cr<-rbind(cr,data.frame(class=cl,precision=pp,recall=rr,f1=ifelse(pp+rr==0,0,2*pp*rr/(pp+rr)),support=sum(ac==cl))) }; cm<-data.frame(); for(a in CLASSES) for(p in CLASSES) cm<-rbind(cm,data.frame(actual=a,predicted=p,n=sum(ac==a&pr==p))); mr<-data.frame(); for(c in c(NUMS,CATS)) mr<-rbind(mr,data.frame(feature=c,missing_fit=sum(is.na(f[[c]])|f[[c]]==""|f[[c]]=="?"),missing_validation=sum(is.na(v[[c]])|v[[c]]==""|v[[c]]=="?"),missing_test=sum(is.na(te[[c]])|te[[c]]==""|te[[c]]=="?"),imputation_value=ifelse(c %in% NUMS,as.character(o$m[[c]]),"missing"))); met<-list(accuracy=mean(ac==pr),macro_f1=mf(ac,pr,CLASSES),log_loss=llm(yt,prob),selected_lambda=sl,validation_log_loss=val$validation_log_loss[bi],n_fit=nrow(f),n_validation=nrow(v),n_test=nrow(te),n_classes=length(CLASSES)); wj(met,file.path(OUT,"metrics.json")); write.csv(pred,file.path(OUT,"predictions.csv"),row.names=FALSE,quote=FALSE); write.csv(cr,file.path(OUT,"class_report.csv"),row.names=FALSE,quote=FALSE); write.csv(cm,file.path(OUT,"confusion_matrix.csv"),row.names=FALSE,quote=FALSE); write.csv(mr,file.path(OUT,"missing_report.csv"),row.names=FALSE,quote=FALSE); write.csv(val,file.path(OUT,"validation_report.csv"),row.names=FALSE,quote=FALSE); wj(list(task_name=TASK_NAME,model_family="ridge_one_vs_rest_softmax",target_column=TARGET,class_order=CLASSES,feature_columns=c(NUMS,CATS),numeric_features=NUMS,categorical_features=CATS,selected_lambda=sl,split_source="split_role",preprocessing_source="fit_rows_only"),file.path(OUT,"model_manifest.json")) }
stability <- stability_refits(f)
write.csv(stability$predictions, file.path(OUT, "stability_refit_predictions.csv"), row.names=FALSE, quote=FALSE)
write.csv(stability$report, file.path(OUT, "stability_refit_report.csv"), row.names=FALSE, quote=FALSE)

if (TASK_KIND == "multiclass") {
  supplied_winner <- val$lambda[order(val$validation_log_loss, val$lambda)][1]
  consensus <- data.frame()
  for (lambda in LAM) {
    stability_count <- sum(stability$report$selected_lambda == lambda)
    total_count <- stability_count + as.integer(supplied_winner == lambda)
    consensus <- rbind(consensus, data.frame(
      lambda=lambda,
      supplied_validation_log_loss=val$validation_log_loss[val$lambda == lambda][1],
      stability_selection_count=stability_count,
      total_selection_count=total_count,
      selection_rate=total_count / 5
    ))
  }
  consensus <- consensus[order(-consensus$total_selection_count, consensus$supplied_validation_log_loss, consensus$lambda), ]
  consensus$selected <- 0L
  consensus$selected[1] <- 1L
  rownames(consensus) <- NULL
  write.csv(consensus, file.path(OUT, "robust_lambda_consensus_report.csv"), row.names=FALSE, quote=FALSE)

  sl <- consensus$lambda[consensus$selected == 1][1]
  b <- mods[[as.character(sl)]]
  baseline_validation_prob <- sm(xv %*% b)
  baseline_validation_pred <- CLASSES[max.col(baseline_validation_prob, ties.method="first")]
  validation_actual <- as.character(v[[TARGET]])
  baseline_validation_log_loss <- llm(yv, baseline_validation_prob)
  baseline_validation_macro_f1 <- mf(validation_actual, baseline_validation_pred, CLASSES)
  feature_drop <- data.frame()
  for (feature in NUMS) {
    keep_terms <- terms != feature
    drop_beta <- ridge(xf[, keep_terms, drop=FALSE], Y, sl)
    drop_prob <- sm(xv[, keep_terms, drop=FALSE] %*% drop_beta)
    drop_pred <- CLASSES[max.col(drop_prob, ties.method="first")]
    drop_log_loss <- llm(yv, drop_prob)
    drop_macro_f1 <- mf(validation_actual, drop_pred, CLASSES)
    feature_drop <- rbind(feature_drop, data.frame(
      feature=feature,
      n_terms=sum(keep_terms),
      validation_log_loss=round(drop_log_loss, 6),
      validation_macro_f1=round(drop_macro_f1, 6),
      delta_log_loss=round(drop_log_loss - baseline_validation_log_loss, 6),
      delta_macro_f1=round(drop_macro_f1 - baseline_validation_macro_f1, 6),
      stringsAsFactors=FALSE
    ))
  }
  feature_drop <- feature_drop[order(-feature_drop$delta_log_loss, feature_drop$delta_macro_f1, feature_drop$feature), ]
  feature_drop$rank <- seq_len(nrow(feature_drop))
  pair_drop <- data.frame()
  for (pair_id in names(PROTEIN_PAIRS)) {
    pair_features <- PROTEIN_PAIRS[[pair_id]]
    keep_terms <- !(terms %in% pair_features)
    drop_beta <- ridge(xf[, keep_terms, drop=FALSE], Y, sl)
    drop_prob <- sm(xv[, keep_terms, drop=FALSE] %*% drop_beta)
    drop_pred <- CLASSES[max.col(drop_prob, ties.method="first")]
    drop_log_loss <- llm(yv, drop_prob)
    drop_macro_f1 <- mf(validation_actual, drop_pred, CLASSES)
    pair_drop <- rbind(pair_drop, data.frame(
      pair_id=pair_id,
      feature_a=pair_features[[1]],
      feature_b=pair_features[[2]],
      n_terms=sum(keep_terms),
      validation_log_loss=round(drop_log_loss, 6),
      validation_macro_f1=round(drop_macro_f1, 6),
      delta_log_loss=round(drop_log_loss - baseline_validation_log_loss, 6),
      delta_macro_f1=round(drop_macro_f1 - baseline_validation_macro_f1, 6),
      stringsAsFactors=FALSE
    ))
  }
  pair_drop <- pair_drop[order(-pair_drop$delta_log_loss, pair_drop$delta_macro_f1, pair_drop$pair_id), ]
  pair_drop$rank <- seq_len(nrow(pair_drop))
  prob <- sm(xt %*% b)
  predicted_index <- max.col(prob, ties.method="first")
  pr <- CLASSES[predicted_index]
  ac <- as.character(te[[TARGET]])
  probability_columns <- paste0("proba_", safe(CLASSES))
  pred <- data.frame(row_id=te$row_id, actual=ac, predicted=pr)
  for (i in seq_along(probability_columns)) pred[[probability_columns[[i]]]] <- prob[, i]
  pred$split_role <- te$split_role
  pred <- pred[order(pred$row_id), ]
  class_report <- data.frame()
  for (class_name in CLASSES) {
    true_positive <- sum(ac == class_name & pr == class_name)
    false_positive <- sum(ac != class_name & pr == class_name)
    false_negative <- sum(ac == class_name & pr != class_name)
    precision <- ifelse(true_positive + false_positive == 0, 0, true_positive / (true_positive + false_positive))
    recall <- ifelse(true_positive + false_negative == 0, 0, true_positive / (true_positive + false_negative))
    class_report <- rbind(class_report, data.frame(
      class=class_name,
      precision=precision,
      recall=recall,
      f1=ifelse(precision + recall == 0, 0, 2 * precision * recall / (precision + recall)),
      support=sum(ac == class_name)
    ))
  }
  confusion <- data.frame()
  for (actual_class in CLASSES) {
    for (predicted_class in CLASSES) {
      confusion <- rbind(confusion, data.frame(
        actual=actual_class,
        predicted=predicted_class,
        n=sum(ac == actual_class & pr == predicted_class)
      ))
    }
  }
  metrics <- list(
    accuracy=mean(ac == pr),
    macro_f1=mf(ac, pr, CLASSES),
    log_loss=llm(yt, prob),
    selected_lambda=sl,
    validation_log_loss=val$validation_log_loss[val$lambda == sl][1],
    n_fit=nrow(f),
    n_validation=nrow(v),
    n_test=nrow(te),
    n_classes=length(CLASSES)
  )
  wj(metrics, file.path(OUT, "metrics.json"))
  write.csv(pred, file.path(OUT, "predictions.csv"), row.names=FALSE, quote=FALSE)
  write.csv(class_report, file.path(OUT, "class_report.csv"), row.names=FALSE, quote=FALSE)
  write.csv(confusion, file.path(OUT, "confusion_matrix.csv"), row.names=FALSE, quote=FALSE)
  write.csv(feature_drop[, c("feature", "n_terms", "validation_log_loss", "validation_macro_f1", "delta_log_loss", "delta_macro_f1", "rank")],
            file.path(OUT, "feature_drop_refit_report.csv"), row.names=FALSE, quote=FALSE)
  write.csv(pair_drop[, c("pair_id", "feature_a", "feature_b", "n_terms", "validation_log_loss", "validation_macro_f1", "delta_log_loss", "delta_macro_f1", "rank")],
            file.path(OUT, "protein_pair_drop_refit_report.csv"), row.names=FALSE, quote=FALSE)
  wj(list(
    task_name=TASK_NAME,
    model_family="ridge_one_vs_rest_softmax",
    target_column=TARGET,
    class_order=CLASSES,
    feature_columns=c(NUMS, CATS),
    numeric_features=NUMS,
    categorical_features=CATS,
    selected_lambda=sl,
    split_source="split_role",
    preprocessing_source="fit_rows_only"
  ), file.path(OUT, "model_manifest.json"))
  write.csv(
    boundary_refit_report(f, te, o, sl, prob, pr),
    file.path(OUT, "boundary_refit_report.csv"),
    row.names=FALSE,
    quote=FALSE
  )
  write.csv(
    paired_boundary_reselection_report(f, v, te, o, prob, pr),
    file.path(OUT, "paired_boundary_reselection_report.csv"),
    row.names=FALSE,
    quote=FALSE
  )
}
