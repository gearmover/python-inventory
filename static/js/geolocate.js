/*
<p><button onclick="geoFindMe()">Show my location</button></p>
<div id="out"></div>
*/

function GeoLocator() {
        var self = this;

        self.alive = false;
        self.position = {'latitude':0,'longitude':0,'accuracy': 999,'elevation':0, 'speed':0, 'age':0};

        self.config = {};
        self.config.minAccuracy = 100;	// 50 meters, easily achieved


        // wraps a quick and dirty call to google maps
        //   el is the document.node to contain the image object
        self.googleMaps = function(el, latitude, longitude, zoom) {
                var img;
                try {
			zoom = zoom || 15;

                        img = new Image();
                        img.src = "http://maps.googleapis.com/maps/api/staticmap?center=" + latitude + "," + longitude + "&zoom="+zoom+"&size=300x300&sensor=false";

                        el = el || document.body;

                        el.innerHTML = '';
                        el.appendChild(img);
                }
                catch(e) {
                        el = el || document.querySelector('body');

                        el.innerHTML = el.innerHTML + '<div style="width:300px;height:300px;background-color:grey;" class="danger">Unable to Communicate with Google Maps</div>';
                        console.warn('GeoLocator.googleMap: Unable to download Google Map. '+e);

                        return;
                }

                return img;
        }


	// Code originally from https://thedotproduct.org/experiments/geo/

	// This function just adds a leading "0" to time/date components which are <10
	function format_time_component(time_component)
	{
		if(time_component<10)
			time_component="0"+time_component;
		else if(time_component.length<2)
			time_component=time_component+"0";

		return time_component;
	}

        // called by the browser whenever new position data is available (and the API is start()ed)
        function geo_success(position) {

		// Check that the accuracy of our Geo location is sufficient for our needs
		if(position.coords.accuracy <= self.config.minAccuracy)
		{
			// We don't want to action anything if our position hasn't changed - we need this because on IPhone Safari at least, we get repeated readings of the same location with
			// different accuracy which seems to count as a different reading - maybe it's just a very slightly different reading or maybe altitude, accuracy etc has changed
			if(Number(self.config.latitude) != position.coords.latitude || Number(self.config.longitude) != position.coords.longitude)
			{
				self.position.speed = position.coords.speed;
				self.position.elevation = position.coords.altitude;
				self.position.latitude = position.coords.latitude;
				self.position.longitude = position.coords.longitude;
				self.position.accuracy = Math.round(position.coords.accuracy,1);

				self.position.age = position.timestamp;

				self.alive = true;
			}

		}
		else
			console.log('GeoLocate.geo_success: bad accuracy for current location.  waiting for better data.');
	}

	// tracks browser/geolocation errors
	function geo_fail(error) {
		switch(error.code) {
		case error.TIMEOUT:
			console.log('GeoLocate.geo_fail: request to Google map server timed out.  Are you connected to the internet?');
		}
	}

        // starts tracking the users position
        self.start = function() {
                // check if geolocation is even supported
                if (!navigator.geolocation) {
                        console.warning('GeoLocator.start: Geolocation either not supported by this browser, or has been disabled.');
                        self.alive = false;
                        return;
                }

                // check if we're already running, if so, restart
                if (self.config.wpid) {
                        if (!self.stop()) {
                                // something failed
                                console.error('GeoLocator.start: unable to restart Geo Watcher as requested.');
                                self.alive = false;
                                return;
                        }
                }

                self.config.wpid = navigator.geolocation.watchPosition(geo_success, geo_fail, { maximumAge: 100000});
		self.alive = true;
        }

	// stops monitoring the users position
	self.stop = function() {
		// check if we're running
		if (!self.config.wpid)
			return;

		navigator.geolocation.clearWatch(self.config.wpid);

		self.alive = false;
	}

	return self;
}