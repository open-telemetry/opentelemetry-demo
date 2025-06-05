<cfset system = createobject("java", "java.lang.System")>
<cfset env = system.getEnv()>
<cfset headers = GetHttpRequestData().headers>

<cfoutput>
    <h1>Hello Cruel World!</h1>

    <p>
        Lucee #server.lucee.version# released #dateformat(server.lucee["release-date"], "dd mmm yyyy")#<br>
    #server.servlet.name# (java #server.java.version#) running on #server.os.name# (#server.os.version#)<br>
    Hosted at #headers.host#
    </p>


    <h2>Server Internals</h2>

    <cfoutput><p>As at #now()#</p></cfoutput>

    <h3>Environment Variables</h3>
    <cfdump var="#env#" label="system.getEnv()">

    <h3>Cookie Variables</h3>
    <cfdump var="#cookie#" label="Cookie">

    <h3>Server Variables</h3>
    <cfdump var="#server#" label="Server">

    <h3>CGI Variables</h3>
    <cfdump var="#cgi#" label="CGI">

    <h3>HTTP Request Variables</h3>
    <cfdump var="#headers#" label="GetHttpRequestData().headers">

</cfoutput>