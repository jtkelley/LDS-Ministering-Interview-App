// Basic Flutter widget test for Ministering Interviews app

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ministering_app/main.dart';

void main() {
  testWidgets('App launches and shows loading screen', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const MinisteringApp());

    // Verify that the loading screen shows the app icon
    expect(find.byIcon(Icons.calendar_month), findsOneWidget);
  });
}
