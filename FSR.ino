#define NUM_SENSORS 13

int sensorPins[NUM_SENSORS] = {A0, A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12};
int fsrReading;
float fsrVoltage;
unsigned long fsrResistance;
unsigned long fsrConductance;
float fsrForce;

void setup() {
    Serial.begin(9600);
}

void loop() {
    String output = ""; // Store CSV data

    for (int i = 0; i < NUM_SENSORS; i++) {
        fsrReading = analogRead(sensorPins[i]);
        fsrVoltage = fsrReading * (5000.0 / 1023.0); // Convert to mV

        if (fsrVoltage == 0) {
            fsrForce = 0; // No pressure
        } else {
            fsrResistance = (5000 - fsrVoltage) * 10000 / fsrVoltage; // Compute resistance
            fsrConductance = 1000000 / fsrResistance; // Conductance in microMhos

            // Use FSR graphs to estimate force (N)
            if (fsrConductance <= 1000) {
                fsrForce = fsrConductance / 80.0;
            } else {
                fsrForce = (fsrConductance - 1000) / 30.0;
            }
        }

        output += String(fsrForce, 2); // Convert force to string (2 decimal places)
        if (i < NUM_SENSORS - 1) output += ","; // Add comma separator
    }

    Serial.println(output); // Print CSV output
    delay(100);
}
