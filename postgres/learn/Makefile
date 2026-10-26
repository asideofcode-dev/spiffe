CC ?= cc
CFLAGS ?= -Wall -Wextra -O0 -g

.PHONY: all clean run

all: mini_postmaster mini_backend

mini_postmaster: mini_postmaster.c
	$(CC) $(CFLAGS) -o $@ $<

mini_backend: mini_backend.c
	$(CC) $(CFLAGS) -o $@ $<

# Build, start postmaster on 15432, send one probe, then stop.
run: all
	@./mini_postmaster 15432 > /tmp/mini_pm.out 2>&1 & echo $$! > .pm.pid; \
	sleep 0.2; \
	python3 -c 'import socket;s=socket.create_connection(("127.0.0.1",15432),2);s.sendall(b"learn-c\n");\
print(s.recv(1024).decode(),end="");print(s.recv(1024).decode(),end="");s.close()'; \
	kill `cat .pm.pid` 2>/dev/null; rm -f .pm.pid; echo "---- postmaster log ----"; cat /tmp/mini_pm.out

clean:
	rm -f mini_postmaster mini_backend .pm.pid
