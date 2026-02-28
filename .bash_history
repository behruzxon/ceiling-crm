pwd
ls
alembic --version
alembic current
alembic history | tail -n 20
exit
cd /app
grep -R -n Zakaz apps/bot | head -n 50
grep -R -n "Zakaz berish" apps/bot | head -n 50
grep -R -n order apps/bot/handlers | head -n 50
grep -R -n buyurtma apps/bot/handlers | head -n 50
exit
