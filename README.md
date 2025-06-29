# FitTrack: Fitness Tracking Applicatie
FitTrack is een webapplicatie waarmee gebruikers hun fitnessvoortgang kunnen bijhouden, workout-plannen kunnen maken en oefeningen kunnen beheren. De applicatie ondersteunt gebruikersauthenticatie via Auth0, gewichtlogs, workout-sessies en een zoekfunctie voor oefeningen.

### Projectstructuur

app/: Bevat de Flask-applicatiecode.
main/: Blueprint voor de hoofdfunctionaliteit (gebruikersbeheer, workouts, profielbeheer).
__init__.py: Initialiseert de Flask-app en configureert extensies (SQLAlchemy, Flask-Login, Auth0, enz.).
models.py: Definieert database-modellen (User, Exercise, WorkoutPlan, enz.).
routes.py: Bevat de routes voor de applicatie (bijv. /index, /profile, /search_exercise).
forms.py: Definieert formulieren voor gebruikersinvoer (bijv. SearchExerciseForm, WeightForm).


config.py: Configuratie voor de development-omgeving, inclusief database- en Auth0-instellingen.
fittrack.py: Entrypoint voor het starten van de Flask-ontwikkelserver.
seed_exercises.py: Script om oefeningen in de database te laden vanuit een CSV-bestand.
.env.example: Voorbeeld van omgevingsvariabelen voor configuratie.

### Functionaliteit

Gebruikersbeheer: Registratie en inloggen via Auth0, profielbeheer, en onboarding-stappen.
Workout-plannen: Aanmaken, bewerken, archiveren en uitvoeren van workout-plannen.
Oefeningen: Zoeken en bekijken van oefeningen, toevoegen aan workout-plannen.
Gewichtlogs: Bijhouden van gewicht en notities.
Workout-sessies: Loggen van sets, reps en gewichten tijdens workouts.

### Vereisten

Python 3.8+
Docker (voor container-gebaseerde setup)
Een Auth0-account voor authenticatie
SQLite (standaarddatabase voor development) of een andere SQL-database
Vereiste Python-pakketten (zie requirements.txt)

### Installatie en setup (lokale ontwikkeling)

Clone de repository:
git clone <repository-url>
cd fittrack


Maak een virtuele omgeving:
python -m venv venv
source venv/bin/activate  # Op Windows: venv\Scripts\activate


### Installeer afhankelijkheden:
pip install -r requirements.txt


### Configureer omgevingsvariabelen:


Vul .env met je Auth0- en andere instellingen:APP_SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///app.db
AUTH0_DOMAIN=your-auth0-domain.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_CALLBACK_URL=http://localhost:5000/callback
SERVER_HOST=0.0.0.0
SERVER_PORT=5000




### Initialiseer de database:

Voer database-migraties uit:flask db init
flask db migrate
flask db upgrade

om de exercises.csv in te laden in de database moet je deze commando uitvoeren:
python seed_exercises.py



### Configureer omgevingsvariabelen:

Zorg dat je .env-bestand is ingesteld.
Voor een persistente database, zorg dat app.db lokaal bestaat.


Gebruik Docker Compose:

Start de applicatie met:docker-compose up --build


Dit herbouwt en start de container automatisch.


### Gebruik

Inloggen/registreren: Ga naar http://localhost:5000/login of /signup en gebruik of maak je account aan.
Onboarding: Voltooi de onboarding-stappen om je profiel in te stellen (naam, gewicht).
Workouts maken: Ga naar /add_workout om een nieuw workout-plan te maken en oefeningen toe te voegen.
Oefeningen zoeken: Gebruik /search_exercise om oefeningen te vinden en toe te voegen aan je plan.
Gewicht loggen: Voeg gewichtlogs toe via /profile.
Workouts uitvoeren: Start een workout-sessie via /start_workout/<id> en log sets/reps.


