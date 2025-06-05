

<cfscript>
    extURL="https://download.lucee.org/";
    configURL="/lucee/admin.cfm";
    wikiURL="https://docs.lucee.org/index.html";
    gitURL="https://github.com/lucee/Lucee";
    adminURL="#CGI.CONTEXT_PATH#/lucee/admin.cfm";
    webAdminURL="#CGI.CONTEXT_PATH#/lucee/admin/web.cfm";
    serverAdminURL="#CGI.CONTEXT_PATH#/lucee/admin/server.cfm";
    docURL="#CGI.CONTEXT_PATH#/lucee/doc.cfm";
    mailinglistURL="https://dev.lucee.org/";
    profURL="https://lucee.org/get-support/consulting.html";
    issueURL="https://luceeserver.atlassian.net/projects/LDEV/issues";
    newURL="http://docs.lucee.org/guides/lucee-5.html";

    extensionList="https://extension.lucee.org/rest/extension/provider/info?withLogo=false";

    function getAvailableExtensions() {
        http url=extensionList cachedWithin=0.01 result="local.res";
        var extensions=deserializeJson(res.filecontent,false).extensions;
        return extensions;
    }

    function getInstalledExtensions() {
        var qry=extensionlist();
        querySort(qry, "name");
        var data=[:];
        loop query=qry {
        data[qry.id]={version:qry.version,name:qry.name};
}
    return data;
}


        function getConfig() {
        var pc=getPageContext();
        var cf=pc.getConfig();
        var result={};
        result.single=listFirst(server.lucee.version,".")>5 && cf.getMode()==	1;
        result.server=cf.getConfigFile()&"";

        if(!result.single) {

        var dir = cf.getServerConfigDir();
        var srv = dir&"/.CFConfig.json";
        if(!fileExists(srv)) srv=dir&"/config.json";
        result.web=result.server;
        result.server=srv;
}
    return result;
}
        config=getConfig();

</cfscript><cfoutput><!DOCTYPE html>
<html>
<head>
    <title>Lucee Docker</title>
    <link rel="stylesheet" type="text/css" href="assets/css/lib/bootstrap.min.css">
    <link rel="stylesheet" type="text/css" href="http://fonts.googleapis.com/css?family=Open+Sans:400,300,600,700,800">
        <!--[if lte IE 8]><link rel="stylesheet" type="text/css" href="#cgi.context_path#/assets/css/lib/ie8.css"><![endif]-->
    <link rel="stylesheet" type="text/css" href="assets/css/core/_ed07b761.core.min.css">
    <link rel="stylesheet" type="text/css" href="assets/css//json.css">
    <!--[if lt IE 9]>
    <script src="http://html5shiv.googlecode.com/svn/trunk/html5.js"></script>
    <![endif]-->

<style>
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 18px;
    text-align: left;
}

table th, table td {
    padding: 12px 15px;
border: 1px solid ##ddd;
}

table th {
background-color: ##f2f2f2;
        text-align: center;
    }

    table tr:nth-child(even) {
background-color: ##f9f9f9;
    }

    table tr:hover {
background-color: ##f1f1f1;
    }

    table input[type="checkbox"] {
        transform: scale(1.5);
        margin-right: 10px;
    }

    table select {
        padding: 5px;
        font-size: 16px;
    }
    </style>
    </head>
    <body>
    <script>
        function syntaxHighlight(json) {
            if (typeof json != 'string') {
                json = JSON.stringify(json, undefined, 2);
            }
            json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:\s*)?|\b(true|false|null)\b|\d+)/g, function (match) {
                var cls = 'number';
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'key';
                    } else {
                        cls = 'string';
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'boolean';
                } else if (/null/.test(match)) {
                    cls = 'null';
                }
                return '<span class="' + cls + '">' + match + '</span>';
            });
        }


    </script>



    </head>
    <body class="sub-page">
    <div class="main-wrapper">
    <section id="page-banner" class="page-banner">
    <div class="container">
    <div class="banner-content">
    <cfoutput>
            <img src="assets/img/lucee-white.png" alt="Lucee" width="300">
            <h1>Welcome to your Lucee Docker Installation!</h1>
        <p class="lead-text">You are now successfully running Lucee #server.lucee.version# in Docker!</p>
    </cfoutput>
    </div>
    </div>
    </section>
    <section id="contents">
    <div class="container full-width">
    <div class="row">
    <div class="col-md-8 main-content">
    <div class="content-wrap">
    <ul class="listing border-light">

    <cfoutput>
            <h1>Customize Your Own Docker Build</h1>
            <p>
                Personalize your Docker build by selecting the extensions you need.
                Lucee will generate a zip file containing all the necessary components for you to create a custom Docker build.
                Follow the steps to choose your desired extensions and configurations,
                ensuring your Docker build is tailored to your specific requirements.
            </p>



        <li class="listing-item thumb-large">
        <div class="listing-thumb">
                <a href="#extURL#">
        <img src="assets/img/img-ext.png" alt="">
    </a>
    </div>


    <div class="listing-content">
    <h2 class="title">
            <a href="#extURL#">Select Your Extensions</a>
    </h2>
        <p>Choose the extensions you would like to include in your Lucee Docker Build.
            Don't forget to select the desired version for each extension.</p>

        <p>Lucee comes with several built-in extensions. You can unselect any that you do not need,
            but please be careful not to remove extensions unless you are sure they are unnecessary,
            as some extensions may be essential for certain functionalities.</p>

        <p><table border="0">
        <thead>
        <tr>
            <th></th>
            <th>Version</th>
            <th>Name</th>
        </tr>
        </thead>
        <cfset extensions=getAvailableExtensions()>
        <cfset installed=getInstalledExtensions()>
        <cfloop query="#extensions#" >

            <cfset hasMatch=structKeyExists(installed,extensions.id)>
            <cfset installData=hasMatch?installed[extensions.id]:{version:""}>
                <tr>
                <td><input name="name" value="#extensions.id#" type="checkbox"  <cfif hasMatch>checked</cfif> ></td>
            <td><select name="version">
                    <option <cfif installData.version EQ extensions.version>selected</cfif>  value="#extensions.version#">latest (#extensions.version#)</option>
                <cfloop array="#extensions.older#" item="v">
                        <option  <cfif installData.version EQ v>selected</cfif> value="#v#">#v#</option></cfloop>
                </select></td>
                <td>#extensions.name#</td>

            </tr>





        </cfloop>
        </table>
            </p>
        </div>
            <div class="clearfix"></div>
        </li>





        <li class="listing-item thumb-large">
        <div class="listing-thumb">
                <a href="#configURL#">
        <img src="assets/img/img-config.png" alt="">
    </a>
    </div>
    <div class="listing-content">
    <h2 class="title">
            <a href="#configURL#">Configuration</a>
    </h2>
        <p>
            To customize your Lucee setup, visit the <a href="/lucee/admin.cfm">Lucee Administrator</a>. Here, you can change the configuration settings to match your specific requirements. Make sure to review all the settings carefully to ensure they meet your needs.
        </p>
        <p>
            Below is a preview of your current configuration.
            You can modify these settings directly in the Lucee Administrator.
        </p>
    <pre class="json-display" id="jsons">#fileRead(config.server)#</pre>
        <button class="copy-button">Create Docker Build</button>
    </div>


        <div class="clearfix"></div>
    </li>




    </cfoutput>
    </ul>
    </div>


    </div>


    <div class="col-md-4 sidebar">

    <div class="sidebar-wrap">
    <cfoutput>
            <div class="widget widget-text">

                <h3 class="widget-title">General Information</h3>
            <p>#server.coldfusion.productname# #server.lucee.version#<br>
            Mode: #config.single?"Single":"Multi"#<br>
            OS: #server.os.name# #server.os.version?:""# (#server.os.archModel#bit)<br>
            Java: #server.java.version?:""# (#server.java.vendor?:""#)<br>
            Time Zone: #getTimeZone()#<br>
            Locale: #ucFirst(GetLocale())#</p>
            
            <p>
                <a href="debug.cfm">View Debug Info</a>
            </p>


            <h3 class="widget-title">Related Websites</h3>

<!--- lucee.org --->
                <p class="file-link"><a href="http://www.lucee.org">Lucee Association Switzerland</a></p>
                <p>Non-profit custodians and maintainers of the Lucee Project</p>


<!--- lucee.org --->
                <p class="file-link"><a href="https://github.com/lucee/lucee-dockerfiles">Lucee Docker Files</a></p>
                <p>A project that provides the code needed to build and run Lucee Docker instances for your CFML applications.</p>


<!--- Bitbucket
<p class="file-link">Lucee Bitbucket</a></p>
<p>Access the source code and builds</p> --->

<!--- Mailinglist --->
            <p class="file-link"><a href="##">Get Involved</a></p>
        <p>
            Get involved in the Lucee Project!<br />
            - Engage with other Lucee community members via our <a href="#mailinglistURL#">forums/mailing list</a><br />
            - <a href="#issueURL#">Submitting</a> bugs and feature requests<br />
            - <a href="#gitURL#">Contribute</a> to the code<br />
            - <a href="https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=LKLC7KH4JRQ8J&">Support</a> the project<br />
        </p>




<!--- Prof Services --->
            <p class="file-link"><a href="#profURL#">Professional Services</a></p>
            <p>Whether you need installation support or are looking for other professional services. Access our directory of providers</p>





        </div>
    </cfoutput>
    </div>

    </div>


    </div>


    </div>


    </section>




    <footer id="subhead">


    <div class="footer-bot">
    <div class="container">
    <div class="row">
        <div class="col-md-2 col-sm-4">
            <a href="/" class="footer-logo">
                <img src="assets/img/lucee-white.png" alt="Lucee">
            </a>


        </div>


    <div class="col-md-5 col-sm-4">
    <p class="copyright-text">Copyright &copy; #year(now())# by the Lucee Association Switzerland</p>
    </div>




    </div>


    </div>


    </div>


    </footer><!-- End of footer -->

    </div> <!-- End of .main-wrapper -->








            <script src="#cgi.context_path#/assets/js/lib/jquery-1.10.1.min.js"></script>
            <script src="#cgi.context_path#/assets/js/lib/bootstrap.min.js"></script>
            <script src="#cgi.context_path#/assets/js/core/_38444bee.core.min.js"></script>
            <script src="#cgi.context_path#/assets/js/lib/SmoothScroll.js"></script>
    <script>

    const pres = document.getElementById('jsons');
    pres.innerHTML = syntaxHighlight(pres.innerText);

    <cfif not config.single>
        const prew = document.getElementById('jsonw');
        prew.innerHTML = syntaxHighlight(prew.innerText);
    </cfif>
    </script>
    </body>

    </html></cfoutput>