-- Decides whether a tenant's configured channel rule authorizes a subscriber to
-- read a given sensor channel.

package Admission_Rules is

   function Compile_Rule (Rule : String) return Boolean;

   function Rule_Admits (Channel : String) return Boolean;

end Admission_Rules;
