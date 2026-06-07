BINARY := cli-web
IMAGE  := cli-sandbox

export DOCKER_HOST ?= unix:///Users/alexday/.colima/default/docker.sock

.PHONY: build image all clean test-e2e

all: image build

build:
	GOPROXY=https://proxy.golang.org,direct go build -o $(BINARY) .

image:
	docker build -t $(IMAGE) -f docker/Dockerfile .

clean:
	rm -f $(BINARY)
	rm -rf sessions/

test-e2e: all
	@./test-e2e.sh
