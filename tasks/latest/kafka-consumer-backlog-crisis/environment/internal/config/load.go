package config

import (
	"encoding/json"
	"os"

	"streamkit/internal/model"
)

func LoadWorkloads(path string) (model.WorkloadFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return model.WorkloadFile{}, err
	}
	var work model.WorkloadFile
	if err := json.Unmarshal(data, &work); err != nil {
		return model.WorkloadFile{}, err
	}
	return work, nil
}

type ClusterProfile struct {
	BrokerVersion     string `json:"broker_version"`
	ReplicaFactor     int    `json:"replica_factor"`
	DefaultPartitions int    `json:"default_partitions"`
	GroupProtocol     string `json:"group_protocol"`
	LaneScan          string `json:"lane_scan"`
	FetchCreditMode   string `json:"fetch_credit_mode"`
	MarkStyle         string `json:"mark_style"`
}

func LoadCluster(path string) (ClusterProfile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ClusterProfile{}, err
	}
	var profile ClusterProfile
	if err := json.Unmarshal(data, &profile); err != nil {
		return ClusterProfile{}, err
	}
	return profile, nil
}
