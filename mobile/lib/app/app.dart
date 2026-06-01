import 'package:flutter/material.dart';

import '../features/home/presentation/screens/home_screen.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '智能骨科康复伴侣',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF1D7AFC),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
