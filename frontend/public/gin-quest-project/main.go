package main

import (
	"context"
	"errors"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
)

func run(migrate bool) error {
	cfg, err := loadConfig()
	if err != nil {
		return err
	}
	db, err := openDB(cfg.DBPath)
	if err != nil {
		return err
	}
	pool, err := db.DB()
	if err != nil {
		return err
	}
	defer pool.Close()
	if migrate {
		return db.AutoMigrate(&User{}, &Note{})
	}
	gin.SetMode(gin.ReleaseMode)
	router, err := newRouter(db, cfg.Secret)
	if err != nil {
		return err
	}
	server := &http.Server{
		Addr: cfg.Addr, Handler: router, ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 10 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second,
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	stopped := make(chan struct{})
	go func() {
		defer close(stopped)
		<-ctx.Done()
		deadline, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(deadline); err != nil {
			_ = server.Close()
		}
	}()
	slog.Info("服务启动", "address", cfg.Addr)
	err = server.ListenAndServe()
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		stop()
		<-stopped
		return err
	}
	<-stopped
	slog.Info("服务停止")
	return nil
}

func main() {
	migrate := flag.Bool("migrate", false, "为教学数据库建表，然后退出")
	flag.Parse()
	if err := run(*migrate); err != nil {
		slog.Error("退出", "error", err)
		os.Exit(1)
	}
}
