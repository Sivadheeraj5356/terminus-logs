# Bank term-deposit campaign: fair scoring across education groups

bank_additional.csv holds client-contact records from a Portuguese bank's
direct-marketing campaigns (UCI Bank Marketing, additional edition). Each row has a
stable row_id, client and campaign attributes, five macroeconomic covariates, and
y, whether the client subscribed a term deposit. Rows with a present y are training
data; rows with a blank y are held-out contacts to score.

education is a protected attribute. It must not be used as a model input (see
protected_attribute_note.md). The scores are graded for quality within each
education group, so the model must recover the signal through legitimate mediating
covariates, not by conditioning on education itself.
