package main

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"os"
)

func main() {
	var key [48]byte
	if _, err := rand.Read(key[:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(base64.RawURLEncoding.EncodeToString(key[:]))
}
