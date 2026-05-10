help: ## Prints help for targets with comments
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

build: ## Build the mod
	./gradlew build

refresh: ## Refresh dependencies
	./gradlew --refresh-dependencies

clean: ## Clean build artifacts
	./gradlew clean

gen-sources: ## Generate decompiled sources
	./gradlew genSources

run-client: ## Run Forge client
	./gradlew runClient

run-server: ## Run Forge server
	./gradlew runServer

stop: ## Stop all Gradle daemons
	./gradlew --stop

nuke: ## Nuke all caches and build dirs
	./gradlew --stop
	rm -rf $$GRADLE_HOME/caches/transforms-*
	rm -rf $$GRADLE_HOME/caches/build-cache-*
	find . -type d \( -name ".idea" -o -name ".kotlin" -o -name ".gradle" -o -name "build" -o -name "run" \) -exec rm -rf {} +
