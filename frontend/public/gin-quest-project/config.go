package main

import (
	"errors"
	"os"
)

type Config struct {
	Addr   string
	DBPath string
	Secret []byte
}

func loadConfig() (Config, error) {
	cfg := Config{Addr: os.Getenv("ADDR"), DBPath: os.Getenv("DB_PATH"), Secret: []byte(os.Getenv("JWT_SECRET"))}
	if cfg.Addr == "" {
		cfg.Addr = "127.0.0.1:8080"
	}
	if cfg.DBPath == "" {
		cfg.DBPath = "quest.db"
	}
	if len(cfg.Secret) < 32 {
		return Config{}, errors.New("JWT_SECRET 至少需要 32 字节，请用 go run ./cmd/key 生成随机密钥")
	}
	return cfg, nil
}
