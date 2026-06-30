import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';

class TriageScreen extends StatefulWidget {
  const TriageScreen({super.key});

  @override
  State<TriageScreen> createState() => _TriageScreenState();
}

class _TriageScreenState extends State<TriageScreen> {
  final TextEditingController _symptomsController = TextEditingController();
  bool _isLoading = false;
  Map<String, dynamic>? _result;
  String _error = '';

  Future<void> _analyze() async {
    if (_symptomsController.text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _error = '';
      _result = null;
    });

    try {
      final response = await ApiService().client.post(
        '/triage/analyze',
        data: {
          'symptoms_text': _symptomsController.text,
          'patient_id': '1', // Hardcoded for demo, normally from token
          'age': 30,
        }
      );
      
      setState(() {
        _result = response.data;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to analyze symptoms. Please try again.';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
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
          'AI Symptom Checker',
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
                'Describe your symptoms in detail:',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF2D3748)),
              ),
              const SizedBox(height: 16),
              
              // Neumorphic TextArea
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
                  controller: _symptomsController,
                  maxLines: 5,
                  decoration: const InputDecoration(
                    hintText: 'E.g., I have had a high fever for 3 days with a dry cough...',
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.all(20),
                  ),
                ),
              ),
              const SizedBox(height: 32),
              
              GestureDetector(
                onTap: _isLoading ? null : _analyze,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF2DD4BF), // Teal
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    ],
                  ),
                  child: Center(
                    child: _isLoading 
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text('Analyze with AI', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                ),
              ),

              if (_error.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(_error, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
              ],

              if (_result != null) ...[
                const SizedBox(height: 48),
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Severity Score', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                          Text(
                            '${_result!['severity_score']}/100', 
                            style: TextStyle(
                              fontWeight: FontWeight.bold, 
                              fontSize: 18,
                              color: _result!['severity_score'] > 50 ? Colors.red : Colors.green
                            )
                          ),
                        ],
                      ),
                      const Divider(height: 32),
                      const Text('Predicted Department', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                      const SizedBox(height: 4),
                      Text(_result!['predicted_condition'], style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                      
                      const Divider(height: 32),
                      const Text('Doctor Recommendation', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                      const SizedBox(height: 4),
                      Text(_result!['doctor_recommendation'], style: const TextStyle(fontSize: 16)),
                    ],
                  ),
                )
              ]
            ],
          ),
        ),
      ),
    );
  }
}
