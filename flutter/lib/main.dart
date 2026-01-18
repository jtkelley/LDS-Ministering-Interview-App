import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config/api_config.dart';
import 'services/api_service.dart';
import 'providers/auth_provider.dart';
import 'providers/members_provider.dart';
import 'screens/login_screen.dart';
import 'screens/member_list_screen.dart';

void main() {
  runApp(const MinisteringApp());
}

class MinisteringApp extends StatelessWidget {
  const MinisteringApp({super.key});

  @override
  Widget build(BuildContext context) {
    // Create API service instance that will be shared
    final apiService = ApiService();

    return MultiProvider(
      providers: [
        // Provide API service
        Provider<ApiService>.value(value: apiService),

        // Auth provider
        ChangeNotifierProvider<AuthProvider>(
          create: (_) => AuthProvider(apiService),
        ),

        // Members provider
        ChangeNotifierProvider<MembersProvider>(
          create: (_) => MembersProvider(apiService),
        ),
      ],
      child: MaterialApp(
        title: 'Ministering Interviews',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
          useMaterial3: true,
          appBarTheme: const AppBarTheme(
            centerTitle: true,
            elevation: 1,
          ),
        ),
        home: const AuthWrapper(),
      ),
    );
  }
}

/// Wrapper that checks auth state and shows appropriate screen
class AuthWrapper extends StatefulWidget {
  const AuthWrapper({super.key});

  @override
  State<AuthWrapper> createState() => _AuthWrapperState();
}

class _AuthWrapperState extends State<AuthWrapper> {
  bool _initialized = false;

  @override
  void initState() {
    super.initState();
    _initializeAuth();
  }

  Future<void> _initializeAuth() async {
    // Initialize API config from stored URL
    await ApiConfig.init();
    // Initialize auth state from stored token
    await context.read<AuthProvider>().initialize();
    if (mounted) {
      setState(() {
        _initialized = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_initialized) {
      // Show splash screen while initializing
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.calendar_month,
                size: 80,
                color: Colors.blue,
              ),
              SizedBox(height: 24),
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Loading...'),
            ],
          ),
        ),
      );
    }

    // Check if logged in
    final authProvider = context.watch<AuthProvider>();

    if (authProvider.isLoggedIn) {
      return const MemberListScreen();
    } else {
      return const LoginScreen();
    }
  }
}
