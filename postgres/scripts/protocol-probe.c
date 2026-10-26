#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libpq-fe.h"

static const char *status_name(ExecStatusType s)
{
    switch (s) {
    case PGRES_EMPTY_QUERY: return "PGRES_EMPTY_QUERY";
    case PGRES_COMMAND_OK: return "PGRES_COMMAND_OK";
    case PGRES_TUPLES_OK: return "PGRES_TUPLES_OK";
    case PGRES_COPY_OUT: return "PGRES_COPY_OUT";
    case PGRES_COPY_IN: return "PGRES_COPY_IN";
    case PGRES_BAD_RESPONSE: return "PGRES_BAD_RESPONSE";
    case PGRES_NONFATAL_ERROR: return "PGRES_NONFATAL_ERROR";
    case PGRES_FATAL_ERROR: return "PGRES_FATAL_ERROR";
    default: return "?";
    }
}

static void run_sql(PGconn *conn, const char *label, const char *sql)
{
    PGresult *res;
    int i, j, nt, nf;
    char *err;

    printf("\n===== %s =====\n", label);
    printf("SQL: %s\n", sql);
    fflush(stdout);
    res = PQexec(conn, (char *)sql);
    if (!res) {
        printf("RESULT: NULL  err=%s\n", PQerrorMessage(conn));
        return;
    }
    printf("STATUS: %s (%d)\n", status_name(PQresultStatus(res)),
           (int)PQresultStatus(res));
    if (PQcmdStatus(res) && PQcmdStatus(res)[0])
        printf("CMDSTATUS: %s\n", PQcmdStatus(res));
    err = PQerrorMessage(conn);
    if (err && err[0] &&
        (PQresultStatus(res) == PGRES_FATAL_ERROR ||
         PQresultStatus(res) == PGRES_NONFATAL_ERROR ||
         PQresultStatus(res) == PGRES_BAD_RESPONSE))
        printf("ERROR: %s", err);
    nt = PQntuples(res);
    nf = PQnfields(res);
    printf("TUPLES: %d  FIELDS: %d\n", nt, nf);
    if (nf > 0) {
        printf("COLUMNS:");
        for (j = 0; j < nf; j++)
            printf(" %s", PQfname(res, j));
        printf("\n");
    }
    for (i = 0; i < nt && i < 25; i++) {
        printf("ROW[%d]:", i);
        for (j = 0; j < nf; j++) {
            char *v = PQgetvalue(res, i, j);
            printf(" %s=%s", PQfname(res, j), v ? v : "(null)");
        }
        printf("\n");
    }
    if (nt > 25)
        printf("... (%d more rows omitted)\n", nt - 25);
    PQclear(res);
}

int main(int argc, char **argv)
{
    const char *port = (argc > 1) ? argv[1] : "15432";
    const char *db = (argc > 2) ? argv[2] : "template1";
    PGconn *conn;
    FILE *tracef;

    printf("===== CONNECT =====\n");
    printf("host=localhost port=%s db=%s PGUSER=%s\n",
           port, db, getenv("PGUSER") ? getenv("PGUSER") : "(unset)");

    conn = PQsetdb("localhost", (char *)port, NULL, NULL, (char *)db);
    printf("PQstatus=%s\n",
           PQstatus(conn) == CONNECTION_OK ? "CONNECTION_OK" : "CONNECTION_BAD");
    if (PQstatus(conn) == CONNECTION_BAD) {
        printf("error: %s\n", PQerrorMessage(conn));
        return 1;
    }
    printf("PQdb=%s PQhost=%s PQport=%s\n",
           PQdb(conn), PQhost(conn), PQport(conn));

    tracef = fopen("/tmp/pg95/artifacts/libpq-trace.log", "w");
    if (tracef)
        PQtrace(conn, tracef);

    run_sql(conn, "list databases", "select * from pg_database");
    run_sql(conn, "list users", "select * from pg_user");
    run_sql(conn, "count classes", "select count(*) from pg_class");
    run_sql(conn, "sample relation names", "select relname from pg_class");
    run_sql(conn, "list type names", "select typname from pg_type");

    run_sql(conn, "constant select", "select 1");
    run_sql(conn, "string constant", "select 'hello'");
    run_sql(conn, "now()", "select now()");

    run_sql(conn, "create table",
            "create table probe_demo (id int4, name text)");
    run_sql(conn, "insert row 1",
            "insert into probe_demo values (1, 'alpha')");
    run_sql(conn, "insert row 2",
            "insert into probe_demo values (2, 'beta')");
    run_sql(conn, "select table", "select * from probe_demo");
    run_sql(conn, "update",
            "update probe_demo set name = 'ALPHA' where id = 1");
    run_sql(conn, "select after update", "select * from probe_demo");
    run_sql(conn, "delete", "delete from probe_demo where id = 2");
    run_sql(conn, "select after delete", "select * from probe_demo");

    run_sql(conn, "syntax error", "SELEC");
    run_sql(conn, "missing relation", "select * from no_such_table");
    run_sql(conn, "empty query", "");
    run_sql(conn, "select after errors", "select * from probe_demo");
    run_sql(conn, "drop table", "drop table probe_demo");

    if (tracef) {
        PQuntrace(conn);
        fclose(tracef);
    }
    printf("\n===== DISCONNECT =====\n");
    PQfinish(conn);
    printf("done\n");
    return 0;
}
