package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"decoder-bot/internal/bot"
)

func main() {
	token := os.Getenv("BOT_TOKEN")
	if token == "" {
		log.Fatal("BOT_TOKEN tidak ditemukan")
	}

	b, err := bot.NewBot(token)
	if err != nil {
		log.Fatal(err)
	}

	go b.Start()

	log.Println("Bot Online")

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	log.Println("Bot Stop")
}
