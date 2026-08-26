package failpoint
import ("fmt"; "os")
func Hit(name string) error {
    if os.Getenv("VAULT_QUALIFY_FAILPOINT") == name { return fmt.Errorf("failpoint %s", name) }
    return nil
}
