<cfcomponent>
    <cffunction name="handle" returntype="string" output="false" access="remote">
        <cfloop from="1" to="20" index="i">
            <cfoutput>
                <!---<cfdump var="#server#" label="Server Scope">--->
                <cfloop from="1" to="1000" index="j">
                    <cfdirectory
                            action="list"
                            directory="/"
                            sort="directory ASC"
                            name="REQUEST.FileQuery"
                            recurse="false"
                            />
                    <cfdump var=#REQUEST.FileQuery#>
                </cfloop>
            </cfoutput>
        </cfloop>
        return "error handled";
    </cffunction>
</cfcomponent>