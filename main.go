package main

import (
	"context"
	"log"
	"os"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func main() {

	pool, err := pgxpool.New(
		context.Background(),
		os.Getenv("DATABASE_URL"),
	)

	if err != nil {
		log.Fatal(err)
	}

	defer pool.Close()

	bot, err := tgbotapi.NewBotAPI(
		os.Getenv("BOT_TOKEN"),
	)

	if err != nil {
		log.Fatal(err)
	}

	log.Println("Bot Online")

	_ = pool
	_ = bot
}
