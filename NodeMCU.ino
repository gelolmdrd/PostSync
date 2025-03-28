#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

#define NUM_SENSORS 13 // Number of pressure sensors

const char *ssid = "been chillin";   // Change to your WiFi SSID
const char *password = "123abcoleg"; // Change to your WiFi Password

ESP8266WebServer server(80);                     // Web server on port 80
String sensorData = "0,0,0,0,0,0,0,0,0,0,0,0,0"; // Default sensor values

unsigned long lastWiFiCheck = 0;                     // Track last WiFi reconnection check
const unsigned long WIFI_RECONNECT_INTERVAL = 10000; // Reconnect every 10 seconds

// Handle HTTP request for sensor data
void handleSensorData()
{
  server.send(200, "text/plain", sensorData);
}

// Handle HTTP request to trigger haptic feedback
void handleHapticTrigger()
{
  if (server.hasArg("trigger"))
  {
    String triggerValue = server.arg("trigger");

    if (triggerValue == "1" || triggerValue == "0")
    {
      Serial.println(triggerValue); // Send trigger value to Arduino Mega
      server.send(200, "text/plain", "Haptic Trigger Sent: " + triggerValue);
    }
    else
    {
      server.send(400, "text/plain", "Invalid 'trigger' value. Use '1' to activate, '0' to deactivate.");
    }
  }
  else
  {
    server.send(400, "text/plain", "Missing 'trigger' parameter");
  }
}

// Function to reconnect WiFi if disconnected
void checkWiFiConnection()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("WiFi disconnected! Reconnecting...");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
  }
}

void setup()
{
  Serial.begin(9600);         // Use a higher baud rate for better data transmission
  WiFi.begin(ssid, password); // Connect to WiFi

  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.print("ESP8266 IP Address: ");
  Serial.println(WiFi.localIP()); // Print IP for reference

  server.on("/get_data", handleSensorData);
  server.on("/haptic", handleHapticTrigger); // Endpoint for haptic feedback trigger
  server.begin();
  Serial.println("HTTP server started.");
}

void loop()
{
  server.handleClient(); // Handle incoming HTTP requests

  // Check WiFi Connection every 10 seconds
  if (millis() - lastWiFiCheck > WIFI_RECONNECT_INTERVAL)
  {
    lastWiFiCheck = millis();
    checkWiFiConnection();
  }

  // Read sensor data from Arduino Mega
  if (Serial.available())
  {
    sensorData = Serial.readStringUntil('\n'); // Read incoming data
    sensorData.trim();                         // Remove extra spaces or newline characters
    Serial.println("Received: " + sensorData); // Debugging
  }
}
