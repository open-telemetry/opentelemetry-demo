component {

this.Name = "Quote CF";
this.applicationTimeout = createTimeSpan(0,2,0,0);
this.sessionManagement = true;
this.sessionTimeout = createTimeSpan(0,0,30,0);
this.setClientCookies = true;

//this.monitoring.showDebug = true;
//this.monitoring.showDoc = true;
//this.monitoring.showMetric = true;


}