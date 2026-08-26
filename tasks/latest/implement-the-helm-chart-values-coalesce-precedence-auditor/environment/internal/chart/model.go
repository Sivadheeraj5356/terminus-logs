package chart

type Dependency struct {
	Name      string
	Version   string
	Condition string
	Alias     string
}

type Chart struct {
	Name         string
	Version      string
	Dependencies []Dependency
}

func (d Dependency) ManifestID() string {
	if d.Alias != "" {
		return d.Alias
	}
	return d.Name
}
