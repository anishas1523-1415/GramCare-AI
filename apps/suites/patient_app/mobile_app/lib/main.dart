import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

void main() {
  runApp(const GramCarePatientApp());
}

class GramCarePatientApp extends StatelessWidget {
  const GramCarePatientApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GramCare Patient App',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: const PatientHybridShell(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class PatientHybridShell extends StatefulWidget {
  const PatientHybridShell({super.key});

  @override
  State<PatientHybridShell> createState() => _PatientHybridShellState();
}

class _PatientHybridShellState extends State<PatientHybridShell> {
  late final WebViewController controller;

  @override
  void initState() {
    super.initState();
    controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0x00000000))
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progress) {
            // Update loading bar.
          },
          onPageStarted: (String url) {},
          onPageFinished: (String url) {},
          onWebResourceError: (WebResourceError error) {},
          onNavigationRequest: (NavigationRequest request) {
            return NavigationDecision.navigate;
          },
        ),
      )
      ..loadRequest(Uri.parse('http://10.0.2.2:5173')); // React Dev Server (Android Emulator loopback)
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: WebViewWidget(controller: controller),
      ),
    );
  }
}
