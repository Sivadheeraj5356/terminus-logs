/* generated from interface/document.idl */
#ifndef VELLUM_DOCUMENT_H
#define VELLUM_DOCUMENT_H
char *vellum_identity_json(void);
char *vellum_canonical_digest(const char *input); /* requires core */
void vellum_free(char *ptr);
#endif
