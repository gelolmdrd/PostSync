#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

#define NUM_SENSORS 13  // Number of pressure sensors

const char* ssid = "been chillin";  // Change to your WiFi SSID
const char* password = "123abcoleg";  // Change to your WiFi Password

ESP8266WebServer server(80);  // Web server on port 80
String sensorData = "0,0,0,0,0,0,0,0,0,0,0,0,0";  // Default value

// Handle HTTP request for sensor data
void handleSensorData() {
  server.send(200, "text/plain", sensorData);
}

void setup() {
  Serial.begin(9600);     // Receive sensor data from Arduino Mega
  WiFi.begin(ssid, password);  // Connect to WiFi

  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.print("ESP8266 IP Address: ");
  Serial.println(WiFi.localIP());  // Print IP for reference

  server.on("/get_data", handleSensorData);  // API endpoint to get data
  server.begin();
  Serial.println("HTTP server started.");
}

void loop() {
  server.handleClient();  // Handle web requests

  if (Serial.available()) {
    sensorData = Serial.readStringUntil('\n');  // Read sensor data from Arduino
    sensorData.trim();  // Remove extra spaces/newline
    Serial.println("Received: " + sensorData);  // Debugging
  }
}
