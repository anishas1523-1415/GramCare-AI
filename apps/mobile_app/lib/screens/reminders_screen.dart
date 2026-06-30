import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class RemindersScreen extends StatefulWidget {
  const RemindersScreen({super.key});

  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  final List<Map<String, dynamic>> _reminders = [
    {
      'medicine': 'Paracetamol 500mg',
      'time': '08:00 AM',
      'taken': false,
      'instructions': 'Take after food'
    },
    {
      'medicine': 'Amoxicillin 250mg',
      'time': '02:00 PM',
      'taken': true,
      'instructions': 'Take with water'
    },
    {
      'medicine': 'Paracetamol 500mg',
      'time': '08:00 PM',
      'taken': false,
      'instructions': 'Take after food'
    }
  ];

  void _toggleReminder(int index) {
    setState(() {
      _reminders[index]['taken'] = !_reminders[index]['taken'];
    });
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
          'Medicine Reminders',
          style: TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: ListView.builder(
          padding: const EdgeInsets.all(24),
          itemCount: _reminders.length,
          itemBuilder: (context, index) {
            final reminder = _reminders[index];
            final isTaken = reminder['taken'];
            
            return GestureDetector(
              onTap: () => _toggleReminder(index),
              child: Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: const Color(0xFFE0E5EC),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: isTaken ? const [] : const [
                    BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                    BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                  ],
                ),
                child: Row(
                  children: [
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: isTaken ? Colors.green : Colors.transparent,
                        shape: BoxShape.circle,
                        border: Border.all(color: isTaken ? Colors.green : Colors.grey, width: 2),
                      ),
                      child: isTaken ? const Icon(Icons.check, color: Colors.white, size: 20) : null,
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            reminder['medicine'],
                            style: TextStyle(
                              fontWeight: FontWeight.bold, 
                              fontSize: 18,
                              color: isTaken ? Colors.grey : const Color(0xFF2D3748),
                              decoration: isTaken ? TextDecoration.lineThrough : null,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${reminder['time']} — ${reminder['instructions']}',
                            style: TextStyle(color: isTaken ? Colors.grey : const Color(0xFF718096)),
                          )
                        ],
                      ),
                    ),
                    Icon(Icons.notifications_active, color: isTaken ? Colors.grey.withOpacity(0.5) : const Color(0xFF3B82F6)),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
