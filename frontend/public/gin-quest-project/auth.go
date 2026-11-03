package main

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type App struct {
	db        *gorm.DB
	secret    []byte
	dummyHash []byte
}

type Credentials struct {
	Email    string `json:"email" binding:"required,email,max=254"`
	Password string `json:"password" binding:"required"`
}

func (a *App) register(c *gin.Context) {
	var input Credentials
	if err := c.ShouldBindJSON(&input); err != nil {
		fail(c, 400, "请求字段无效")
		return
	}
	if len(input.Password) < 12 || len(input.Password) > 72 {
		fail(c, 400, "密码需要 12 到 72 字节")
		return
	}
	email := strings.ToLower(strings.TrimSpace(input.Email))
	hash, err := bcrypt.GenerateFromPassword([]byte(input.Password), bcrypt.DefaultCost)
	if err != nil {
		fail(c, 500, "密码处理失败")
		return
	}
	user := User{Email: email, PasswordHash: string(hash)}
	result := a.db.WithContext(c.Request.Context()).Clauses(clause.OnConflict{
		Columns: []clause.Column{{Name: "email"}}, DoNothing: true,
	}).Create(&user)
	if result.Error != nil {
		fail(c, 500, "保存用户失败")
		return
	}
	if result.RowsAffected == 0 {
		fail(c, 409, "邮箱已被注册")
		return
	}
	c.JSON(http.StatusCreated, gin.H{"id": user.ID, "email": user.Email})
}

func (a *App) login(c *gin.Context) {
	var input Credentials
	if err := c.ShouldBindJSON(&input); err != nil {
		fail(c, 400, "请求字段无效")
		return
	}
	if len(input.Password) > 72 {
		fail(c, 401, "邮箱或密码错误")
		return
	}
	var user User
	err := a.db.WithContext(c.Request.Context()).Where("email = ?", strings.ToLower(strings.TrimSpace(input.Email))).First(&user).Error
	if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
		fail(c, 500, "查询用户失败")
		return
	}
	hash := []byte(user.PasswordHash)
	if errors.Is(err, gorm.ErrRecordNotFound) {
		hash = a.dummyHash
	}
	passwordErr := bcrypt.CompareHashAndPassword(hash, []byte(input.Password))
	if err != nil || passwordErr != nil {
		fail(c, 401, "邮箱或密码错误")
		return
	}
	now := time.Now()
	claims := jwt.RegisteredClaims{
		Subject: strconv.FormatUint(uint64(user.ID), 10), Issuer: "gin-quest",
		Audience: jwt.ClaimStrings{"gin-quest-client"},
		IssuedAt: jwt.NewNumericDate(now), ExpiresAt: jwt.NewNumericDate(now.Add(15 * time.Minute)),
	}
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(a.secret)
	if err != nil {
		fail(c, 500, "签发凭证失败")
		return
	}
	c.JSON(200, gin.H{"access_token": token, "token_type": "Bearer", "expires_in": 900})
}

func (a *App) authenticate() gin.HandlerFunc {
	return func(c *gin.Context) {
		parts := strings.Fields(c.GetHeader("Authorization"))
		if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
			fail(c, 401, "需要有效登录凭证")
			return
		}
		claims := &jwt.RegisteredClaims{}
		token, err := jwt.ParseWithClaims(parts[1], claims, func(token *jwt.Token) (interface{}, error) {
			return a.secret, nil
		}, jwt.WithValidMethods([]string{"HS256"}), jwt.WithIssuer("gin-quest"),
			jwt.WithAudience("gin-quest-client"), jwt.WithExpirationRequired(), jwt.WithIssuedAt())
		if err != nil || !token.Valid {
			fail(c, 401, "凭证无效或已过期")
			return
		}
		id, err := strconv.ParseUint(claims.Subject, 10, 32)
		if err != nil || id == 0 {
			fail(c, 401, "凭证无效")
			return
		}
		var user User
		err = a.db.WithContext(c.Request.Context()).First(&user, uint(id)).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			fail(c, 401, "用户不存在")
			return
		}
		if err != nil {
			fail(c, 503, "暂时无法验证用户")
			return
		}
		c.Set("userID", uint(id))
		c.Next()
	}
}
