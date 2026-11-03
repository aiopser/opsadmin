package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

func newRouter(db *gorm.DB, secret []byte) (*gin.Engine, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte("dummy-password-not-a-user"), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	a := &App{db: db, secret: secret, dummyHash: hash}
	router := gin.New()
	if err := router.SetTrustedProxies(nil); err != nil {
		return nil, err
	}
	// 进程启动时设置一次，运行中不要并发修改全局解码设置。
	binding.EnableDecoderDisallowUnknownFields = true
	router.HandleMethodNotAllowed = true
	router.Use(gin.CustomRecoveryWithWriter(io.Discard, func(c *gin.Context, recovered interface{}) {
		slog.Error("请求异常", "request_id", c.GetString("requestID"))
		fail(c, 500, "内部错误")
	}))
	router.Use(func(c *gin.Context) {
		var bytes [16]byte
		if _, err := rand.Read(bytes[:]); err != nil {
			fail(c, 500, "初始化请求失败")
			return
		}
		id := hex.EncodeToString(bytes[:])
		c.Set("requestID", id)
		c.Header("X-Request-ID", id)
		c.Header("X-Content-Type-Options", "nosniff")
		c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, 16<<10)
		started := time.Now()
		c.Next()
		slog.Info("request", "id", id, "method", c.Request.Method, "route", c.FullPath(), "status", c.Writer.Status(), "duration", time.Since(started))
	})
	router.NoRoute(func(c *gin.Context) { fail(c, 404, "路由不存在") })
	router.NoMethod(func(c *gin.Context) { fail(c, 405, "请求方法不支持") })
	router.GET("/healthz", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })
	router.GET("/readyz", func(c *gin.Context) {
		pool, err := db.DB()
		if err != nil {
			fail(c, 503, "数据库未就绪")
			return
		}
		ctx, cancel := context.WithTimeout(c.Request.Context(), time.Second)
		defer cancel()
		if err := pool.PingContext(ctx); err != nil {
			fail(c, 503, "数据库未就绪")
			return
		}
		c.JSON(200, gin.H{"status": "ready"})
	})
	api := router.Group("/api/v1")
	api.POST("/auth/register", a.register)
	api.POST("/auth/login", a.login)
	notes := api.Group("/notes", a.authenticate())
	notes.GET("", a.listNotes)
	notes.POST("", a.createNote)
	notes.GET("/:id", a.getNote)
	notes.PATCH("/:id", a.updateNote)
	notes.DELETE("/:id", a.deleteNote)
	return router, nil
}
