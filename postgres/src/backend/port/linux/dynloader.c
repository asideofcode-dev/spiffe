/*-------------------------------------------------------------------------
 *
 * dynloader.c -- dynamic loader for Linux
 *
 * Original Postgres95 used GNU dld. Modern Linux ELF uses dlopen(3).
 * When LINUX_ELF is defined, port-protos.h already maps pg_dl* to dlfcn;
 * this file provides fallbacks if something still references the symbols.
 *
 *-------------------------------------------------------------------------
 */
#include <stdio.h>
#include <string.h>

#ifdef LINUX_ELF
#include <dlfcn.h>
#else
#include <dld.h>
#endif

#include "postgres.h"
#include "port-protos.h"
#include "utils/elog.h"
#include "fmgr.h"

#ifndef LINUX_ELF
extern char pg_pathname[];
#endif

void *
pg_dlopen(char *filename)
{
#ifdef LINUX_ELF
    return dlopen(filename, RTLD_LAZY);
#else
    static int dl_initialized = 0;

    if (!dl_initialized) {
	if (dld_init(dld_find_executable(pg_pathname)))
	    return NULL;
	dl_initialized = 1;
    }

    if (dld_link(filename))
	return NULL;

    if (dld_undefined_sym_count > 0) {
	if (dld_link("/usr/lib/libc.a")) {
	    elog(NOTICE, "dld: Cannot link C library!");
	    return NULL;
	}
	if (dld_undefined_sym_count > 0) {
	    if (dld_link("/usr/lib/libm.a")) {
		elog(NOTICE, "dld: Cannot link math library!");
		return NULL;
	    }
	    if (dld_undefined_sym_count > 0) {
		int count = dld_undefined_sym_count;
		char **list = dld_list_undefined_sym();

		elog(NOTICE, "dld: Undefined:");
		do {
		    elog(NOTICE, "  %s", *list);
		    list++;
		    count--;
		} while (count > 0);

		dld_unlink_by_file(filename, 1);
		return NULL;
	    }
	}
    }

    return (void *) strdup(filename);
#endif
}

char *
pg_dlerror(void)
{
#ifdef LINUX_ELF
    return (char *) dlerror();
#else
    return dld_strerror(dld_errno);
#endif
}
