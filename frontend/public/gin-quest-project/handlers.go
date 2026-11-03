package main

import (
	"errors"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func fail(c *gin.Context, status int, message string) {
	c.AbortWithStatusJSON(status, gin.H{"error": gin.H{"message": message}})
}

func userID(c *gin.Context) (uint, bool) {
	value, exists := c.Get("userID")
	id, ok := value.(uint)
	if !exists || !ok {
		fail(c, 401, "请先登录")
		return 0, false
	}
	return id, true
}

func parseID(c *gin.Context) (uint, bool) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil || id == 0 {
		fail(c, 400, "id 必须是正整数")
		return 0, false
	}
	return uint(id), true
}

func (a *App) listNotes(c *gin.Context) {
	uid, ok := userID(c)
	if !ok {
		return
	}
	var query struct {
		Page int `form:"page,default=1" binding:"min=1,max=100000"`
		Size int `form:"size,default=10" binding:"min=1,max=100"`
	}
	if err := c.ShouldBindQuery(&query); err != nil {
		fail(c, 400, "分页参数无效")
		return
	}
	base := a.db.WithContext(c.Request.Context()).Model(&Note{}).Where("owner_id = ?", uid)
	var total int64
	if err := base.Count(&total).Error; err != nil {
		fail(c, 500, "统计失败")
		return
	}
	var notes []Note
	if err := base.Order("id DESC").Offset((query.Page - 1) * query.Size).Limit(query.Size).Find(&notes).Error; err != nil {
		fail(c, 500, "查询失败")
		return
	}
	items := make([]NoteView, 0, len(notes))
	for _, note := range notes {
		items = append(items, noteView(note))
	}
	c.JSON(200, gin.H{"items": items, "total": total, "page": query.Page, "size": query.Size})
}

func (a *App) createNote(c *gin.Context) {
	uid, ok := userID(c)
	if !ok {
		return
	}
	var input struct {
		Title string `json:"title" binding:"required,max=120"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		fail(c, 400, "title 需要 1 到 120 个字符")
		return
	}
	title := strings.TrimSpace(input.Title)
	if title == "" {
		fail(c, 400, "标题不能为空白")
		return
	}
	note := Note{OwnerID: uid, Title: title}
	if err := a.db.WithContext(c.Request.Context()).Create(&note).Error; err != nil {
		fail(c, 500, "保存失败")
		return
	}
	c.Header("Location", "/api/v1/notes/"+strconv.FormatUint(uint64(note.ID), 10))
	c.JSON(201, noteView(note))
}

func (a *App) findNote(c *gin.Context) (Note, bool) {
	uid, ok := userID(c)
	if !ok {
		return Note{}, false
	}
	id, ok := parseID(c)
	if !ok {
		return Note{}, false
	}
	var note Note
	err := a.db.WithContext(c.Request.Context()).Where("id = ? AND owner_id = ?", id, uid).First(&note).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		fail(c, 404, "任务不存在")
		return Note{}, false
	}
	if err != nil {
		fail(c, 500, "查询失败")
		return Note{}, false
	}
	return note, true
}

func (a *App) getNote(c *gin.Context) {
	note, ok := a.findNote(c)
	if ok {
		c.JSON(200, noteView(note))
	}
}

func (a *App) updateNote(c *gin.Context) {
	note, ok := a.findNote(c)
	if !ok {
		return
	}
	var input struct {
		Title *string `json:"title" binding:"omitempty,max=120"`
		Done  *bool   `json:"done"`
	}
	if err := c.ShouldBindJSON(&input); err != nil {
		fail(c, 400, "请求字段无效")
		return
	}
	updates := make(map[string]interface{})
	if input.Title != nil {
		title := strings.TrimSpace(*input.Title)
		if title == "" {
			fail(c, 400, "标题不能为空白")
			return
		}
		updates["title"] = title
	}
	if input.Done != nil {
		updates["done"] = *input.Done
	}
	if len(updates) == 0 {
		fail(c, 400, "请至少提交 title 或 done")
		return
	}
	result := a.db.WithContext(c.Request.Context()).Model(&Note{}).Where("id = ? AND owner_id = ?", note.ID, note.OwnerID).Updates(updates)
	if result.Error != nil {
		fail(c, 500, "更新失败")
		return
	}
	if result.RowsAffected == 0 {
		fail(c, 404, "任务不存在")
		return
	}
	note, ok = a.findNote(c)
	if ok {
		c.JSON(200, noteView(note))
	}
}

func (a *App) deleteNote(c *gin.Context) {
	note, ok := a.findNote(c)
	if !ok {
		return
	}
	result := a.db.WithContext(c.Request.Context()).Where("id = ? AND owner_id = ?", note.ID, note.OwnerID).Delete(&Note{})
	if result.Error != nil {
		fail(c, 500, "删除失败")
		return
	}
	if result.RowsAffected == 0 {
		fail(c, 404, "任务不存在")
		return
	}
	c.Status(204)
}
