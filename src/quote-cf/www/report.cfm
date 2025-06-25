<cfscript>

    int = randRange(1,20,'SHA1PRNG');

    for (i=1; i <= int; i++) {
        int2 = randRange(6,97,'SHA1PRNG');
        int3 = randRange(12343,21389,'SHA1PRNG');

        writeLog(
            text="Info: Processing quote " & int3 & " - Records processed " & int2,
            type="error",
            application="no",
            file="exception");

        sleep(50);
    }

    sleep(150);

    writeLog(
        text="java.lang.OutOfMemoryError: Java heap space",
        type="error",
        application="no",
        file="exception");

    writeLog(
        text="Exiting Process: pid 1",
        type="error",
        application="no",
        file="exception");

</cfscript>