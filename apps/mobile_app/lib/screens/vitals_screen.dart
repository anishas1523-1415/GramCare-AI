import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'dart:math';

class VitalsScreen extends StatefulWidget {
  const VitalsScreen({super.key});

  @override
  State<VitalsScreen> createState() => _VitalsScreenState();
}

class _VitalsScreenState extends State<VitalsScreen> {
  final TextEditingController _heartRateController = TextEditingController();
  final TextEditingController _spO2Controller = TextEditingController();
  
  bool _isStreaming = false;

  void _simulateBLEConnection() {
    setState(() {
      _isStreaming = true;
      _heartRateController.text = (60 + Random().nextInt(40)).toString();
      _spO2Controller.text = (95 + Random().nextInt(5)).toString();
    });
    
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Connected to Smartwatch (BLE Simulation)'),
        backgroundColor: Color(0xFF10B981),
      )
    );
  }

  void _submitVitals() {
    // In production, we push to the offline sync queue or transmit via Socket.io
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Vitals recorded successfully.'),
        backgroundColor: Color(0xFF10B981),
      )
    );
    context.pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFE0E5EC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF2D3748)),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'IoT Vitals Monitor',
          style: TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Sync your smartwatch or input manually:',
                style: TextStyle(fontSize: 16, color: Color(0xFF718096)),
              ),
              const SizedBox(height: 24),
              
              // BLE Sync Button
              GestureDetector(
                onTap: _simulateBLEConnection,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B82F6), // Blue
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    ],
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.bluetooth, color: Colors.white),
                      const SizedBox(width: 8),
                      Text(
                        _isStreaming ? 'Streaming Live...' : 'Connect Smartwatch (BLE)', 
                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 48),

              // Heart Rate Input
              const Text('Heart Rate (bpm)', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF2D3748))),
              const SizedBox(height: 8),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFE0E5EC),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: const [
                    BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                  ],
                ),
                child: TextField(
                  controller: _heartRateController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    hintText: 'e.g. 72',
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.all(20),
                    suffixIcon: Icon(Icons.favorite, color: Colors.red),
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // SpO2 Input
              const Text('SpO2 (%)', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF2D3748))),
              const SizedBox(height: 8),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFFE0E5EC),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: const [
                    BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                  ],
                ),
                child: TextField(
                  controller: _spO2Controller,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    hintText: 'e.g. 98',
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.all(20),
                    suffixIcon: Icon(Icons.air, color: Colors.blue),
                  ),
                ),
              ),

              const SizedBox(height: 48),

              // Submit Button
              GestureDetector(
                onTap: _submitVitals,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981), // Green
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    ],
                  ),
                  child: const Center(
                    child: Text('Save Vitals', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                ),
              ),

            ],
          ),
        ),
      ),
    );
  }
}
