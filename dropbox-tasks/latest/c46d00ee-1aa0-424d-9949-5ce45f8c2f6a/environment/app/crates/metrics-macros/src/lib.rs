use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, DeriveInput};

#[proc_macro_derive(RecordMetric)]
pub fn record_metric_derive(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    let name = input.ident;
    let expanded = quote! {
        impl #name {
            pub fn metric_name(&self) -> &'static str {
                stringify!(#name)
            }
        }
    };
    expanded.into()
}
