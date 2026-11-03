package main

import (
	"time"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type User struct {
	ID           uint   `gorm:"primaryKey"`
	Email        string `gorm:"size:254;uniqueIndex;not null"`
	PasswordHash string `gorm:"not null" json:"-"`
	CreatedAt    time.Time
}

type Note struct {
	ID        uint   `gorm:"primaryKey"`
	OwnerID   uint   `gorm:"index;not null"`
	Title     string `gorm:"size:120;not null"`
	Done      bool   `gorm:"not null;default:false"`
	CreatedAt time.Time
	UpdatedAt time.Time
	DeletedAt gorm.DeletedAt `gorm:"index" json:"-"`
}

// 仅返回接口需要的字段，数据库模型不直接成为响应契约。
type NoteView struct {
	ID        uint      `json:"id"`
	Title     string    `json:"title"`
	Done      bool      `json:"done"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

func noteView(n Note) NoteView {
	return NoteView{ID: n.ID, Title: n.Title, Done: n.Done, CreatedAt: n.CreatedAt, UpdatedAt: n.UpdatedAt}
}

func openDB(path string) (*gorm.DB, error) {
	db, err := gorm.Open(sqlite.Open(path), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		return nil, err
	}
	pool, err := db.DB()
	if err != nil {
		return nil, err
	}
	// SQLite 教学版限制一个连接，降低多写者锁冲突；生产选型需重新评估。
	pool.SetMaxOpenConns(1)
	pool.SetMaxIdleConns(1)
	return db, nil
}
