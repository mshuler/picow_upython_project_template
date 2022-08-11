let wifiSSIDField = document.getElementById("ssid");
let showPassCB = document.getElementById("showPassCB");
let wifiPasswordField = document.getElementById("pass");
let scannedWifiNetworksField = document.getElementById("swifinetworks");
let wifiNetworksField = document.getElementById("wifinetworks");
let rssiField = document.getElementById("rssiField");
let channelField = document.getElementById("channelField");
let saveWifiSettingsButton = document.getElementById("save");
let networkList = []
let selectedWiFiNetworkIndex = 0;

var log = function(msg) {
   $('<span/>').html(msg + '\n').appendTo('#result')
};
	  	
showPassCB.addEventListener("click", function() {
    if (wifiPasswordField.type === "password") {
        wifiPasswordField.type = "text";
    } else {
        wifiPasswordField.type = "password";
    }
});   

function updateSelectedNetwork(){
    return function(){
	     let network = networkList[wifiNetworksField.selectedIndex];
	     channelField.value = network[2];
	     rssiField.value = network[3];
	     wifiSSIDField.value = network[0];
    }
}

wifiNetworksField.addEventListener("click", function() {
	setTimeout(updateSelectedNetwork(), 2000);
});

function ssidOK() {
	 if( wifiSSIDField.value.length < 8 ) {
	 	alert("The SSID must be at least 8 characters long.");
	 	return 0;
	 }
	 else {
    	return 1;
	 }
}

function passwordOK() {
	// Password can be left unset for open networks
 	return 1;
}

function saveWiFiSettings() {
    console.log("PJA: SAVE WIFI SETTINGS");
}

window.onload = function(){
   let nStrings = scannedWifiNetworksField.value.split(",");
   for( index in nStrings) {
   	elems = nStrings[index].split(":");
   	networkList.push(elems);
   	wifiNetworksField.add(new Option(elems[0]));
   	console.log( elems );
   }
}