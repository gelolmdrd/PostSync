#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

const char *ssid = "been chillin";
const char *password = "123abcoleg";

ESP8266WebServer server(80);
String sensorData = "0,0,0,0,0,0,0,0,0,0,0,0,0";

void handleSensorData()
{
  server.send(200, "text/plain", sensorData);
}

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
      server.send(400, "text/plain", "Invalid 'trigger' value. Use '1' or '0'.");
    }
  }
  else
  {
    server.send(400, "text/plain", "Missing 'trigger' parameter");
  }
}

void setup()
{
  Serial.begin(9600);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());

  server.on("/get_data", handleSensorData);
  server.on("/haptic", handleHapticTrigger);
  server.begin();
}

void loop()
{
  server.handleClient();

  if (Serial.available())
  {
    sensorData = Serial.readStringUntil('\n');
    sensorData.trim(); // Clean up newline characters
    Serial.println("Received Sensor Data: " + sensorData);
  }
}
