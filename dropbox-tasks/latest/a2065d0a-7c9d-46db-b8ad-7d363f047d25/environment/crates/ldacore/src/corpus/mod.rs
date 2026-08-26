use crate::model::{CorpusStaging, RawDoc, StagedDoc};
use crate::vocab;
use anyhow::{bail, Result};
use std::collections::BTreeMap;

pub fn build(docs: Vec<RawDoc>) -> Result<CorpusStaging> {
    if docs.is_empty() {
        bail!("no documents to stage");
    }
    for doc in &docs {
        if doc.doc_id.is_empty() {
            bail!("doc_id must be non-empty");
        }
        if doc.tokens.is_empty() {
            bail!("document token list must be non-empty");
        }
        for token in &doc.tokens {
            if token.is_empty() {
                bail!("tokens must be non-empty");
            }
        }
    }
    let vocabulary = vocab::build(&docs);
    let index: BTreeMap<&str, usize> = vocabulary
        .iter()
        .enumerate()
        .map(|(i, t)| (t.as_str(), i))
        .collect();
    let staged: Vec<StagedDoc> = docs
        .iter()
        .map(|doc| StagedDoc {
            doc_id: doc.doc_id.clone(),
            token_ids: doc.tokens.iter().map(|t| index[t.as_str()]).collect(),
        })
        .collect();
    Ok(CorpusStaging {
        schema: "lda-corpus/v1".into(),
        vocab: vocabulary,
        docs: staged,
    })
}
