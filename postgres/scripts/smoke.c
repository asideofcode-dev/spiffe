/* Minimal Postgres95 client smoke test against a running postmaster. */
#include <stdio.h>
#include <stdlib.h>
#include "libpq-fe.h"

int
main(int argc, char **argv)
{
    const char *port = (argc > 1) ? argv[1] : "15432";
    PGconn *conn;
    PGresult *res;
    int i, j;

    conn = PQsetdb("localhost", (char *)port, NULL, NULL, "template1");
    if (PQstatus(conn) == CONNECTION_BAD) {
	fprintf(stderr, "connection failed: %s\n", PQerrorMessage(conn));
	return 1;
    }
    printf("connected to postmaster on port %s\n", port);

    res = PQexec(conn, "select * from pg_database");
    if (!res) {
	fprintf(stderr, "exec failed: %s\n", PQerrorMessage(conn));
	PQfinish(conn);
	return 1;
    }
    printf("status=%d tuples=%d fields=%d\n",
	   PQresultStatus(res), PQntuples(res), PQnfields(res));
    for (i = 0; i < PQntuples(res); i++) {
	for (j = 0; j < PQnfields(res); j++)
	    printf("%s=%s ", PQfname(res, j), PQgetvalue(res, i, j));
	printf("\n");
    }
    PQclear(res);
    PQfinish(conn);
    return 0;
}
