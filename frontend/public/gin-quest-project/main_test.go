package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

var testSecret = []byte("test-only-secret-must-not-be-used-in-production")

func setup(t *testing.T) http.Handler {
	t.Helper()
	gin.SetMode(gin.TestMode)
	db, err := openDB(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	pool, err := db.DB()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = pool.Close() })
	if err := db.AutoMigrate(&User{}, &Note{}); err != nil {
		t.Fatal(err)
	}
	router, err := newRouter(db, testSecret)
	if err != nil {
		t.Fatal(err)
	}
	return router
}

func request(h http.Handler, method, path, body, token string) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	h.ServeHTTP(rec, req)
	return rec
}

func account(t *testing.T, h http.Handler, email string) string {
	t.Helper()
	body := `{"email":"` + email + `","password":"correct-password-123"}`
	rec := request(h, "POST", "/api/v1/auth/register", body, "")
	if rec.Code != 201 {
		t.Fatalf("register: %d %s", rec.Code, rec.Body)
	}
	rec = request(h, "POST", "/api/v1/auth/login", body, "")
	if rec.Code != 200 {
		t.Fatalf("login: %d %s", rec.Code, rec.Body)
	}
	var result struct {
		Token string `json:"access_token"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Token == "" {
		t.Fatal("missing token")
	}
	return result.Token
}

func TestCRUDAndIsolation(t *testing.T) {
	h := setup(t)
	owner := account(t, h, "alice@example.com")
	other := account(t, h, "bob@example.com")
	rec := request(h, "POST", "/api/v1/notes", `{"title":"Learn Gin"}`, owner)
	if rec.Code != 201 {
		t.Fatalf("create: %d %s", rec.Code, rec.Body)
	}
	var created NoteView
	if err := json.Unmarshal(rec.Body.Bytes(), &created); err != nil {
		t.Fatal(err)
	}
	path := "/api/v1/notes/" + strconv.FormatUint(uint64(created.ID), 10)
	for _, method := range []string{"GET", "PATCH", "DELETE"} {
		rec = request(h, method, path, `{"done":true}`, other)
		if rec.Code != 404 {
			t.Fatalf("isolation %s: %d", method, rec.Code)
		}
	}
	for _, value := range []string{"true", "false"} {
		rec = request(h, "PATCH", path, `{"done":`+value+`}`, owner)
		if rec.Code != 200 {
			t.Fatalf("update: %d %s", rec.Code, rec.Body)
		}
		var updated NoteView
		if err := json.Unmarshal(rec.Body.Bytes(), &updated); err != nil {
			t.Fatal(err)
		}
		if updated.Done != (value == "true") {
			t.Fatal("zero-value update lost")
		}
	}
	rec = request(h, "GET", "/api/v1/notes?page=1&size=5", "", other)
	var list struct {
		Items []NoteView `json:"items"`
		Total int64      `json:"total"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &list); err != nil {
		t.Fatal(err)
	}
	if list.Total != 0 || len(list.Items) != 0 {
		t.Fatal("other user's list leaked")
	}
	rec = request(h, "DELETE", path, "", owner)
	if rec.Code != 204 || rec.Body.Len() != 0 {
		t.Fatalf("delete: %d", rec.Code)
	}
	rec = request(h, "GET", path, "", owner)
	if rec.Code != 404 {
		t.Fatal("deleted note still visible")
	}
}

func TestValidationAndAuth(t *testing.T) {
	h := setup(t)
	token := account(t, h, "test@example.com")
	cases := []struct {
		method, path, body, token string
		status                    int
	}{
		{"GET", "/api/v1/notes", "", "", 401},
		{"GET", "/api/v1/notes", "", "tampered", 401},
		{"GET", "/api/v1/notes?page=0", "", token, 400},
		{"GET", "/api/v1/notes?size=101", "", token, 400},
		{"GET", "/api/v1/notes/abc", "", token, 400},
		{"POST", "/api/v1/notes", `{"title":"   "}`, token, 400},
		{"POST", "/api/v1/notes", `{"title":"x","owner_id":2}`, token, 400},
		{"POST", "/api/v1/notes", `{"title":123}`, token, 400},
		{"POST", "/api/v1/notes", `{"title":"` + strings.Repeat("x", 17000) + `"}`, token, 400},
		{"POST", "/api/v1/auth/register", `{"email":"test@example.com","password":"correct-password-123"}`, "", 409},
		{"POST", "/api/v1/auth/register", `{"email":"other@example.com","password":"short"}`, "", 400},
		{"POST", "/api/v1/auth/login", `{"email":"test@example.com","password":"wrong-password"}`, "", 401},
		{"GET", "/missing", "", "", 404},
		{"PUT", "/api/v1/notes", "", token, 405},
	}
	for i, tc := range cases {
		t.Run(strconv.Itoa(i), func(t *testing.T) {
			rec := request(h, tc.method, tc.path, tc.body, tc.token)
			if rec.Code != tc.status {
				t.Fatalf("got %d want %d: %s", rec.Code, tc.status, rec.Body)
			}
			if rec.Header().Get("X-Request-ID") == "" {
				t.Fatal("missing request id")
			}
		})
	}
}

func TestExpiredAndWrongAlgorithm(t *testing.T) {
	h := setup(t)
	_ = account(t, h, "jwt@example.com")
	for _, method := range []jwt.SigningMethod{jwt.SigningMethodHS256, jwt.SigningMethodHS384} {
		claims := jwt.RegisteredClaims{Subject: "1", Issuer: "gin-quest", Audience: jwt.ClaimStrings{"gin-quest-client"}, ExpiresAt: jwt.NewNumericDate(time.Now().Add(-time.Hour))}
		if method == jwt.SigningMethodHS384 {
			claims.ExpiresAt = jwt.NewNumericDate(time.Now().Add(time.Hour))
		}
		token, err := jwt.NewWithClaims(method, claims).SignedString(testSecret)
		if err != nil {
			t.Fatal(err)
		}
		rec := request(h, "GET", "/api/v1/notes", "", token)
		if rec.Code != 401 {
			t.Fatalf("bad jwt accepted: %d", rec.Code)
		}
	}
}

func TestPersistence(t *testing.T) {
	path := filepath.Join(t.TempDir(), "persist.db")
	db, err := openDB(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := db.AutoMigrate(&Note{}); err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&Note{OwnerID: 1, Title: "Still here"}).Error; err != nil {
		t.Fatal(err)
	}
	pool, err := db.DB()
	if err != nil {
		t.Fatal(err)
	}
	if err := pool.Close(); err != nil {
		t.Fatal(err)
	}
	db, err = openDB(path)
	if err != nil {
		t.Fatal(err)
	}
	pool, err = db.DB()
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	var count int64
	if err := db.Model(&Note{}).Count(&count).Error; err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("persistent count: %d", count)
	}
}
