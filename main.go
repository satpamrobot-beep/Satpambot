package main

import (
	"fmt"
	"net/http"
)

func main() {
	fmt.Println("Bot Online")

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "OK")
	})

	http.ListenAndServe(":8080", nil)
}
